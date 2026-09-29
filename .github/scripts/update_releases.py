"""Refresh the latest-releases section of README.md from the GitHub Releases of my apps."""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

README_PATH = "README.md"
OWNER = "whrss9527"
APPS = {"pop": "Pop", "meno": "Meno", "stox": "Stox", "proxi": "Proxi"}
BEIJING = timezone(timedelta(hours=8))
SECTION = re.compile(r"(<!-- RELEASES:START -->\n).*?(<!-- RELEASES:END -->)", re.DOTALL)


def latest_release(repo):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{OWNER}/{repo}/releases?per_page=10",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "whrss9527-profile-readme"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        releases = [release for release in json.load(response) if not release["draft"]]
    # count prereleases too: Pop has only shipped betas so far, and /releases/latest skips them
    return max(releases, key=lambda release: release["published_at"], default=None)


def render(releases):
    lines = []
    for repo, release in sorted(releases, key=lambda item: item[1]["published_at"], reverse=True):
        published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
        label = f"{APPS[repo]} {release['tag_name']}" + (" 测试版" if release["prerelease"] else "")
        lines.append(
            f'- <img src="assets/icons/{repo}.png" width="16" height="16" align="top" alt=""> '
            f"[{label}]({release['html_url']}) · {published.astimezone(BEIJING):%Y-%m-%d}\n"
        )
    return "".join(lines)


def main():
    releases = [(repo, release) for repo in APPS if (release := latest_release(repo))]
    if not releases:
        raise SystemExit("no releases found, README left unchanged")
    with open(README_PATH, encoding="utf-8") as file:
        readme = file.read()
    readme, count = SECTION.subn(lambda match: match.group(1) + render(releases) + match.group(2), readme)
    if count != 1:
        raise SystemExit("README.md must contain exactly one RELEASES section")
    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(readme)


if __name__ == "__main__":
    main()
