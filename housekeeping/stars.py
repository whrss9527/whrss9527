#!/usr/bin/env python3
"""把 GitHub star 按规则分进 Lists（Stars 页面里的分组）。

需要 Python 3.8+ 和已登录的 GitHub CLI（gh auth login）。

    python3 stars.py export              拉取全部 star，存到 stars.json
    python3 stars.py plan                按 star-lists.json 预览分组，不做任何修改
    python3 stars.py plan --unmatched    只列出规则没覆盖到的仓库，方便补规则
    python3 stars.py apply               创建缺少的 List 并把仓库加进去（只增不减）

打分规则见 star-lists.json 开头的「_说明」。
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STARS_FILE = HERE / "stars.json"
RULES_FILE = HERE / "star-lists.json"

STARS_QUERY = """
query($cursor: String) {
  viewer {
    starredRepositories(first: 100, after: $cursor, orderBy: {field: STARRED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      edges {
        starredAt
        node {
          id nameWithOwner description stargazerCount isArchived isPrivate
          primaryLanguage { name }
          repositoryTopics(first: 20) { nodes { topic { name } } }
        }
      }
    }
  }
}"""

LISTS_QUERY = """
query($cursor: String) {
  viewer {
    lists(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { id name }
    }
  }
}"""

LIST_ITEMS_QUERY = """
query($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on UserList {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { ... on Repository { id } }
      }
    }
  }
}"""

CREATE_LIST = """
mutation($name: String!, $description: String, $isPrivate: Boolean) {
  createUserList(input: {name: $name, description: $description, isPrivate: $isPrivate}) {
    list { id }
  }
}"""

# listIds 是这个仓库最终所属的全部 List（整体覆盖，不是追加），所以调用前要并上它已经在的 List
SET_ITEM_LISTS = """
mutation($itemId: ID!, $listIds: [ID!]!) {
  updateUserListsForItem(input: {itemId: $itemId, listIds: $listIds}) {
    lists { id }
  }
}"""

RATE_LIMIT_HINTS = ("rate limit", "too quickly", "abuse")


def gql(query, **variables):
    body = json.dumps({"query": query, "variables": variables})
    for wait in (60, 120, 300, 600, None):
        try:
            proc = subprocess.run(["gh", "api", "graphql", "--input", "-"], input=body,
                                  capture_output=True, text=True, encoding="utf-8")
        except FileNotFoundError:
            sys.exit("需要 GitHub CLI：https://cli.github.com（装好后运行 gh auth login）")
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            data = {}
        errors = data.get("errors") or []
        if proc.returncode == 0 and not errors:
            return data["data"]
        message = " ".join([proc.stderr.strip()] + [e.get("message", "") for e in errors]).strip()
        if not any(hint in message.lower() for hint in RATE_LIMIT_HINTS):
            sys.exit(f"GitHub API 调用失败：{message}")
        if wait is None:
            sys.exit("多次重试后仍被 GitHub 限流。过一会儿重新运行即可，已经分好的会自动跳过。")
        print(f"  触发 GitHub 限流，{wait} 秒后重试……")
        time.sleep(wait)


def paginate(query, path, key, **variables):
    cursor = None
    while True:
        connection = gql(query, cursor=cursor, **variables)
        for step in path:
            connection = connection[step]
        yield from connection[key]
        if not connection["pageInfo"]["hasNextPage"]:
            return
        cursor = connection["pageInfo"]["endCursor"]


def fetch_stars():
    print("正在拉取 star……")
    stars = []
    for edge in paginate(STARS_QUERY, ["viewer", "starredRepositories"], "edges"):
        node = edge["node"]
        stars.append({
            "repo": node["nameWithOwner"],
            "id": node["id"],
            "description": node["description"] or "",
            "language": (node["primaryLanguage"] or {}).get("name") or "",
            "topics": [t["topic"]["name"] for t in node["repositoryTopics"]["nodes"]],
            "stars": node["stargazerCount"],
            "archived": node["isArchived"],
            "private": node["isPrivate"],
            "starredAt": edge["starredAt"],
        })
    STARS_FILE.write_text(json.dumps(stars, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"共 {len(stars)} 个 star，已保存到 {STARS_FILE.name}")
    return stars


def load_stars(refresh):
    if refresh or not STARS_FILE.exists():
        return fetch_stars()
    return json.loads(STARS_FILE.read_text(encoding="utf-8"))


def keyword_pattern(word):
    word = word.lower()
    if word.isascii():
        # 英文按整词匹配：go 不会命中 google，但会命中 go-zero
        return re.compile(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])")
    return re.compile(re.escape(word))


class Rule:
    def __init__(self, spec):
        self.name = spec["name"]
        self.topics = {t.lower() for t in spec.get("topics", [])}
        self.keywords = [keyword_pattern(k) for k in spec.get("keywords", [])]
        self.languages = {lang.lower() for lang in spec.get("languages", [])}

    def score(self, repo):
        name = repo["repo"].split("/", 1)[1].lower()
        description = repo["description"].lower()
        points = 3 * len(self.topics.intersection(t.lower() for t in repo["topics"]))
        for pattern in self.keywords:
            if pattern.search(name):
                points += 2
            elif pattern.search(description):
                points += 1
        if repo["language"].lower() in self.languages:
            points += 2
        return points


def classify(stars, rules):
    """返回 (List 名 -> 仓库列表, 规则没覆盖到的仓库, overrides 里不在 star 中的仓库)。"""
    lists = [Rule(spec) for spec in rules["lists"]]
    fallback = rules.get("fallback")
    min_score = rules.get("min_score", 2)
    overrides = {repo.lower(): names for repo, names in rules.get("overrides", {}).items()}
    plan = {rule.name: [] for rule in lists}
    if fallback:
        plan.setdefault(fallback["name"], [])
    unmatched = []
    for repo in stars:
        names = overrides.pop(repo["repo"].lower(), None)
        if names is None:
            scores = [rule.score(repo) for rule in lists]
            best = max(range(len(lists)), key=scores.__getitem__)  # 同分时取靠前的 List
            if scores[best] >= min_score:
                names = [lists[best].name]
            else:
                unmatched.append(repo)
                names = [fallback["name"]] if fallback else []
        for name in names:
            plan.setdefault(name, []).append(repo)
    return plan, unmatched, sorted(overrides)


def load_rules():
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def shorten(text, width):
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 1] + "…"


def human(count):
    if count >= 10000:
        return f"★{count // 1000}k"
    if count >= 1000:
        return f"★{count / 1000:.1f}k"
    return f"★{count}"


def cmd_export(args):
    fetch_stars()


def cmd_plan(args):
    stars = load_stars(args.refresh)
    rules = load_rules()
    plan, unmatched, missing = classify(stars, rules)
    by_stars = lambda repo: -repo["stars"]
    if args.unmatched:
        print(f"规则没覆盖到的 {len(unmatched)} 个仓库（在 star-lists.json 里补关键词，或写进 overrides）：")
        for repo in sorted(unmatched, key=by_stars):
            print(f"  {repo['repo']}  [{repo['language'] or '-'}]  {', '.join(repo['topics'][:8])}")
            if repo["description"]:
                print(f"      {shorten(repo['description'], 90)}")
        return
    for name, repos in plan.items():
        if repos:
            print(f"\n{name}（{len(repos)}）")
            for repo in sorted(repos, key=by_stars):
                print(f"  {repo['repo']:<42} {human(repo['stars']):>7}  {shorten(repo['description'], 48)}")
    used = sum(1 for repos in plan.values() if repos)
    summary = f"\n共 {len(stars)} 个 star，分进 {used} 个 List，其中 {len(unmatched)} 个规则没覆盖到"
    if unmatched and rules.get("fallback"):
        summary += f"，放进了「{rules['fallback']['name']}」"
    print(summary)
    if missing:
        print(f"overrides 里这些仓库不在你的 star 中，已忽略：{', '.join(missing)}")
    print("用 plan --unmatched 查看没覆盖到的仓库；满意后运行 apply。")


def cmd_apply(args):
    stars = load_stars(refresh=not args.cached)
    rules = load_rules()
    plan, _, _ = classify(stars, rules)
    specs = {spec["name"]: spec for spec in rules["lists"]}
    if rules.get("fallback"):
        specs.setdefault(rules["fallback"]["name"], rules["fallback"])

    print("正在读取已有的 List……")
    existing = {node["name"]: node["id"] for node in paginate(LISTS_QUERY, ["viewer", "lists"], "nodes")}
    membership = {}  # 仓库 id -> 它现在所在的 List id
    for list_id in existing.values():
        for item in paginate(LIST_ITEMS_QUERY, ["node", "items"], "nodes", id=list_id):
            if item.get("id"):
                membership.setdefault(item["id"], set()).add(list_id)

    wanted = {}  # 仓库 id -> (仓库名, 要进的 List 名)
    for name, repos in plan.items():
        for repo in repos:
            wanted.setdefault(repo["id"], (repo["repo"], set()))[1].add(name)
    to_create = [name for name, repos in plan.items() if repos and name not in existing]
    changes = [
        (repo_id, repo, names) for repo_id, (repo, names) in wanted.items()
        if any(name not in existing or existing[name] not in membership.get(repo_id, ()) for name in names)
    ]

    print(f"要新建 {len(to_create)} 个 List：{'、'.join(to_create) or '无'}")
    print(f"要更新 {len(changes)} 个仓库的分组（已有的 List 和分组都会保留）")
    if not to_create and not changes:
        print("已经是最新状态。")
        return
    if not args.yes and input("输入 yes 开始执行：").strip() != "yes":
        sys.exit("已取消。")

    for name in to_create:
        spec = specs.get(name, {})
        data = gql(CREATE_LIST, name=name, description=spec.get("description", ""),
                   isPrivate=bool(spec.get("private")))
        existing[name] = data["createUserList"]["list"]["id"]
        print(f"  新建 List：{name}")
        time.sleep(args.delay)
    for index, (repo_id, repo, names) in enumerate(changes, 1):
        list_ids = membership.get(repo_id, set()) | {existing[name] for name in names}
        gql(SET_ITEM_LISTS, itemId=repo_id, listIds=sorted(list_ids))
        print(f"  [{index}/{len(changes)}] {repo} → {'、'.join(sorted(names))}")
        time.sleep(args.delay)
    print("完成。")


def main():
    parser = argparse.ArgumentParser(description="按规则把 GitHub star 分进 Lists")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("export", help="拉取全部 star，存到 stars.json").set_defaults(func=cmd_export)
    plan = commands.add_parser("plan", help="预览分组，不做任何修改")
    plan.add_argument("--unmatched", action="store_true", help="只列出规则没覆盖到的仓库")
    plan.add_argument("--refresh", action="store_true", help="先重新拉取 star")
    plan.set_defaults(func=cmd_plan)
    apply = commands.add_parser("apply", help="创建缺少的 List 并把仓库加进去（只增不减）")
    apply.add_argument("--cached", action="store_true", help="直接用已有的 stars.json，不重新拉取")
    apply.add_argument("--yes", action="store_true", help="跳过确认")
    apply.add_argument("--delay", type=float, default=1.0, help="两次修改之间间隔的秒数，默认 1")
    apply.set_defaults(func=cmd_apply)
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # 输出接到 tee 之类的管道时也能实时看到进度
    args.func(args)


if __name__ == "__main__":
    main()
