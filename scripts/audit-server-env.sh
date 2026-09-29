#!/usr/bin/env bash
set -eu

repo_dir="${1:-/opt/taste-yourself/app}"
cd "$repo_dir"
printf 'REV='
git rev-parse --short HEAD 2>/dev/null || true

keys=(
  APP_ENV WECHAT_APP_ID WECHAT_APP_SECRET FASHN_API_KEY DECART_API_KEY
  MIRROR_LLM_BASE_URL MIRROR_LLM_API_KEY MIRROR_LLM_MODEL MIRROR_VISION_MODEL
  MIRROR_ASR_MODEL BODY_SCAN_PROVIDER BODYGRAM_ORG_ID BODYGRAM_API_KEY
  CONTENT_SAFETY_PROVIDER TAOBAO_APP_KEY TAOBAO_APP_SECRET
)

if [[ -f .env ]]; then
  for key in "${keys[@]}"; do
    value="$(sed -n "s/^${key}=//p" .env | tail -n1)"
    if [[ -n "$value" ]]; then
      printf '%s=set\n' "$key"
    else
      printf '%s=missing\n' "$key"
    fi
  done
else
  echo '.env missing'
fi

docker ps --format 'CONTAINER={{.Names}} STATUS={{.Status}}'
