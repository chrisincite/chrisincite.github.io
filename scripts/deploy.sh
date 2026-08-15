#!/usr/bin/env bash
# 觸發 Cloudflare Pages 部署。
#
# 為什麼需要這支：chris-os 這個 Pages 專案是用 API 建的，Cloudflare 沒有在
# GitHub repo 上裝 webhook，所以 push 到 main 「不會」自動部署。
# 要恢復自動部署，得由 Chris 在 Cloudflare 後台重新 Connect to Git 一次
# （會安裝 GitHub App）；在那之前，每次 push 後跑這支。
#
# 用法：bash scripts/deploy.sh [branch]

set -euo pipefail

BRANCH="${1:-main}"
TOKEN_FILE="$HOME/.config/cloudflare/api_token"
ACCOUNT="b38329a6da496cab8f08045175400e8a"
PROJECT="chris-os"

[ -r "$TOKEN_FILE" ] || { echo "讀不到 $TOKEN_FILE" >&2; exit 1; }
TOKEN=$(tr -d '\n\r ' < "$TOKEN_FILE")

API="https://api.cloudflare.com/client/v4/accounts/${ACCOUNT}/pages/projects/${PROJECT}"

echo "→ 觸發部署（branch: ${BRANCH}）"
DEPLOY_ID=$(curl -s -X POST -H "Authorization: Bearer ${TOKEN}" \
  "${API}/deployments" -F "branch=${BRANCH}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["result"]["id"] if d.get("success") else "", file=sys.stdout); print(json.dumps(d.get("errors"),ensure_ascii=False), file=sys.stderr) if not d.get("success") else None')

[ -n "$DEPLOY_ID" ] || { echo "觸發失敗" >&2; exit 1; }
echo "  deployment: ${DEPLOY_ID:0:8}"

for i in $(seq 1 20); do
  sleep 10
  STATUS=$(curl -s -H "Authorization: Bearer ${TOKEN}" "${API}/deployments/${DEPLOY_ID}" \
    | python3 -c 'import json,sys; s=(json.load(sys.stdin)["result"].get("latest_stage") or {}); print("%s %s"%(s.get("name"),s.get("status")))')
  echo "  [$i] ${STATUS}"
  case "$STATUS" in
    "deploy success") echo "✓ 已上線：https://os.housearch.net/"; exit 0 ;;
    *failure*|*canceled*) echo "✗ 部署失敗：${STATUS}" >&2; exit 1 ;;
  esac
done

echo "⚠ 逾時未完成，請自行查看 Cloudflare 後台" >&2
exit 1
