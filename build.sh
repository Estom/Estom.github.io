#!/usr/bin/env bash
# 在build阶段完成数据的处理，生成可部署的产物
set -euo pipefail

# 可选：从当前目录的 .env 加载环境变量（用于本地/CI 注入配置）
# 说明：要求 .env 采用 bash 兼容的 KEY=VALUE 语法；该段会将其导出到子进程。
if [[ -f ".env" ]]; then
	set -a
	# shellcheck disable=SC1091
	source ".env"
	set +a
fi

REPO_URL="${NOTE_REPO_URL}"
NOTES_DIR="notes"
BRANCH="${NOTE_REPO_BRANCH:-master}"

TAG_METHOD="${TAG_METHOD:-textrank}"

if [[ ! -d "$NOTES_DIR" ]]; then
	echo "[notes] $NOTES_DIR not found, cloning from $REPO_URL ..."
	git clone "$REPO_URL" "$NOTES_DIR"
else
	if [[ ! -d "$NOTES_DIR/.git" ]]; then
		echo "[notes] $NOTES_DIR exists but is not a git repository (.git missing)."
		echo "        Will use existing files without git history."
	else
		echo "[notes] updating $NOTES_DIR ($BRANCH) ..."
		git -C "$NOTES_DIR" fetch origin "$BRANCH"
		git -C "$NOTES_DIR" checkout "$BRANCH"
		git -C "$NOTES_DIR" pull --ff-only origin "$BRANCH"
	fi
fi

# 数据处理
uv sync
uv run hexo-sync --verbose
uv run hexo-proc --verbose --git-batch=true --tag-method="$TAG_METHOD" --tag-count=3 --tag-budget=100


# 生成静态文件
npm install
npm run clean
npm run build
