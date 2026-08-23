#!/usr/bin/env bash
# 推送前后安全验证 — 敏感信息扫描 + 远端结构核验
# 用法:
#   ./verify_push.sh pre  [TOKEN]          # 推送前: 暂存区敏感扫描
#   ./verify_push.sh post OWNER REPO [TOKEN]  # 推送后: 远端结构与CI状态
set -euo pipefail

MODE="${1:-}"

# 敏感模式: 密钥/内网域名/联系方式 —— 按需追加自己的规则
SENSITIVE_RE='sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|@(foxmail|gmail|qq|163|139)\.|1[3-9][0-9]{9}|\b[0-9]{5,11}@qq'

scan_staged() {
  echo "=== 推送前: 暂存区敏感信息扫描 ==="
  if git diff --cached | grep -inE "$SENSITIVE_RE"; then
    echo "❌ FAIL: 发现疑似敏感信息（见上）—— 请脱敏后再推送"
    exit 1
  fi
  echo "✅ PASS: 暂存区无敏感信息"
  echo "=== .gitignore 泄露检查（具体目标名会变相暴露） ==="
  if git show :.gitignore 2>/dev/null | grep -vE '^#|^$|^\*|^\.|/$' | grep -qE '[a-z0-9]{6,}[-_/][a-z0-9]'; then
    echo "⚠️ .gitignore 含具体文件/目录名，确认它们不含目标身份信息"
  else
    echo "✅ .gitignore 仅泛化规则"
  fi
}

verify_remote() {
  local OWNER="$1" REPO="$2" TOKEN="${3:-}"
  local AUTH=()
  [[ -n "$TOKEN" ]] && AUTH=(-H "Authorization: token $TOKEN")
  echo "=== 远端文件结构 ==="
  curl -s "https://api.github.com/repos/$OWNER/$REPO/contents/" "${AUTH[@]}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); [print(' ', f['type'][:3], f['path']) for f in d] if isinstance(d,list) else print('❌', d.get('message'))"
  echo "=== CI 最近运行 ==="
  curl -s "https://api.github.com/repos/$OWNER/$REPO/actions/runs?per_page=1" "${AUTH[@]}" \
    | python3 -c "import json,sys; r=json.load(sys.stdin).get('workflow_runs',[]); print(' ', r[0]['name'], r[0]['status'], r[0]['conclusion']) if r else print('  (无运行记录)')"
  echo "=== Topics 与描述 ==="
  curl -s "https://api.github.com/repos/$OWNER/$REPO" "${AUTH[@]}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(' 描述:', (d.get('description') or '')[:80]); print(' ⚠️ 未设置描述' if not d.get('description') else '')"
}

case "$MODE" in
  pre)  scan_staged ;;
  post) [[ $# -ge 3 ]] || { echo "用法: $0 post OWNER REPO [TOKEN]"; exit 1; }
        verify_remote "$2" "$3" "${4:-}" ;;
  *) echo "用法: $0 pre [TOKEN] | $0 post OWNER REPO [TOKEN]"; exit 1 ;;
esac
