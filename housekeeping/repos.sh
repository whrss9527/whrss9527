#!/usr/bin/env bash
# 按 repos.tsv（以及可选的 repos.private.tsv）批量整理 GitHub 仓库。
#
#   bash repos.sh            预览：实时查询 star / fork / 最后推送时间，不做任何修改
#   bash repos.sh --apply    执行归档 / 转私有 / 删除，执行前会再确认一次
#
# 删除仓库需要 delete_repo 权限：gh auth refresh -h github.com -s delete_repo
# 兼容 macOS 自带的 bash 3.2。
set -euo pipefail
cd "$(dirname "$0")"

owner=${OWNER:-whrss9527}
apply=false
case "${1:-}" in
  --apply) apply=true ;;
  "") ;;
  *) echo "用法：bash repos.sh [--apply]" >&2; exit 2 ;;
esac

command -v gh >/dev/null || { echo "需要 GitHub CLI：https://cli.github.com" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "请先登录：gh auth login" >&2; exit 1; }

plans=(repos.tsv)
[ -f repos.private.tsv ] && plans+=(repos.private.tsv)

# 读计划
actions=() repos=() reasons=()
kept=0
while read -r action repo reason; do
  case $action in
    keep) kept=$((kept + 1)); continue ;;
    delete | archive | private | private+archive) ;;
    *) echo "未知动作「$action」（$repo）" >&2; exit 1 ;;
  esac
  actions+=("$action") repos+=("$repo") reasons+=("$reason")
done < <(cat "${plans[@]}" | grep -vE '^[[:space:]]*(#|$)')

# 预览：每个待处理仓库的实时状态记在 states 里（"是否已归档|可见性"）；
# 找不到或已经处理过的记为空，执行时跳过，所以中断后可以直接重跑。
# gh 输出的每一列都不能为空：read 按 tab 切分时会把连续的 tab 合并，导致错位。
states=()
n_delete=0 n_archive=0 n_private=0
printf '\n%-16s %-28s %6s %6s  %-10s  %s\n' ACTION REPO STARS FORKS PUSHED NOTE
for ((i = 0; i < ${#repos[@]}; i++)); do
  action=${actions[i]} repo=${repos[i]} note=${reasons[i]}
  if ! info=$(gh repo view "$owner/$repo" --json stargazerCount,forkCount,pushedAt,isArchived,visibility \
    --jq '[.stargazerCount, .forkCount, (.pushedAt // "-")[0:10], (.isArchived | tostring), .visibility] | @tsv' \
    </dev/null 2>/dev/null); then
    states+=("")
    printf '%-16s %-28s %s\n' "$action" "$repo" "（找不到，可能已经删除，跳过）"
    continue
  fi
  IFS=$'\t' read -r stars forks pushed archived visibility <<<"$info"
  finished=false
  case $action in
    archive) [ "$archived" = true ] && finished=true ;;
    private) [ "$visibility" = PRIVATE ] && finished=true ;;
    private+archive) [ "$visibility" = PRIVATE ] && [ "$archived" = true ] && finished=true ;;
  esac
  if $finished; then
    states+=("")
    printf '%-16s %-28s %s\n' "$action" "$repo" "（已经处理过，跳过）"
    continue
  fi
  states+=("$archived|$visibility")
  case $action in
    delete)
      n_delete=$((n_delete + 1))
      if [ $((stars + forks)) -gt 0 ]; then note="⚠ 有人 star / fork，可以考虑改成 archive；$note"; fi
      ;;
    archive) n_archive=$((n_archive + 1)) ;;
    private*)
      n_private=$((n_private + 1))
      if [ "$stars" -gt 0 ]; then note="⚠ 转私有会清空 star；$note"; fi
      ;;
  esac
  printf '%-16s %-28s %6s %6s  %-10s  %s\n' "$action" "$repo" "$stars" "$forks" "$pushed" "$note"
done

echo
echo "合计：删除 $n_delete · 归档 $n_archive · 转私有 $n_private（另有 $kept 个保留，未列出）"
if ! $apply; then
  echo "以上只是预览。确认无误后执行：bash repos.sh --apply"
  exit 0
fi
if [ $((n_delete + n_archive + n_private)) -eq 0 ]; then
  echo "没有需要处理的仓库。"
  exit 0
fi

if [ "$n_delete" -gt 0 ]; then
  # 能读到 token scopes 时（OAuth 登录）提前检查，避免删到一半才报错
  scopes=$(gh auth status 2>&1 | grep -i 'token scopes' || true)
  if [ -n "$scopes" ] && [[ $scopes != *delete_repo* ]]; then
    echo "删除仓库需要 delete_repo 权限，先运行：gh auth refresh -h github.com -s delete_repo" >&2
    exit 1
  fi
fi
read -r -p "删除后无法撤销（fork 基本恢复不了）。输入 yes 开始执行：" answer
[ "$answer" = yes ] || { echo "已取消。"; exit 1; }

failed=0
run() {
  local label=$1 out
  shift
  if out=$("$@" 2>&1 </dev/null); then
    echo "  ✓ $label"
  else
    echo "  ✗ $label：$out"
    failed=$((failed + 1))
  fi
}
make_private() {
  local out
  # 新版 gh 要求显式确认可见性变更的后果；旧版没有这个参数
  out=$(gh repo edit "$1" --visibility private --accept-visibility-change-consequences 2>&1 </dev/null) && return 0
  case $out in
    *"unknown flag"*) gh repo edit "$1" --visibility private </dev/null ;;
    *) echo "$out"; return 1 ;;
  esac
}

for ((i = 0; i < ${#repos[@]}; i++)); do
  action=${actions[i]} repo=${repos[i]} state=${states[i]}
  [ -n "$state" ] || continue
  archived=${state%%|*} visibility=${state#*|}
  case $action in
    delete) run "删除 $repo" gh repo delete "$owner/$repo" --yes ;;
    archive)
      if [ "$archived" = true ]; then echo "  - $repo 已经是归档状态"; else run "归档 $repo" gh repo archive "$owner/$repo" --yes; fi
      ;;
    private | private+archive)
      if [ "$visibility" = PRIVATE ]; then echo "  - $repo 已经是私有"; else run "转私有 $repo" make_private "$owner/$repo"; fi
      if [ "$action" = private+archive ] && [ "$archived" != true ]; then
        run "归档 $repo" gh repo archive "$owner/$repo" --yes
      fi
      ;;
  esac
done

echo
if [ "$failed" -gt 0 ]; then
  echo "完成，但有 $failed 项失败，见上面的 ✗。修正后可以直接重跑，已处理的会被跳过。"
  exit 1
fi
echo "全部完成。"
