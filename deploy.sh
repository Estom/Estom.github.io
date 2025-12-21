#!/usr/bin/env bash
set -euo pipefail

# Local default: use Hexo's configured deploy (SSH in _config.yml)
# CI (GitHub Actions): build then deploy via HTTPS using a token.

if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
	PAGES_REPO="${PAGES_REPO:-Estom/Estom.github.io}"
	PAGES_BRANCH="${PAGES_BRANCH:-main}"
	DEPLOY_TOKEN="${PAGES_REPO_TOKEN:-${GITHUB_TOKEN:-}}"

	if [[ -z "${DEPLOY_TOKEN}" ]]; then
		echo "[deploy] Missing token. Set secret PAGES_REPO_TOKEN (recommended) or provide GITHUB_TOKEN (only works if deploying to the same repo)." >&2
		exit 1
	fi

	# Install dependencies + generate fresh public/
	npm ci
	npx hexo clean
	npx hexo generate

	# Override deploy target for CI to avoid requiring an SSH key.
	# GitHub will mask secrets in logs, but we also avoid echoing the URL.
	cat > _config.ci.deploy.yml <<EOF
deploy:
  type: git
  repo: https://x-access-token:${DEPLOY_TOKEN}@github.com/${PAGES_REPO}.git
  branch: ${PAGES_BRANCH}
EOF

	npx hexo deploy -c _config.yml,_config.ci.deploy.yml
else
	npm run deploy
fi