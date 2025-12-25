#!/usr/bin/env bash
# 在build阶段完成数据的处理，生成可部署的产物
set -euo pipefail

REPO_URL="${REPO_URL:-https://gitee.com/Eyestorm/notes.git}"
NOTES_DIR="notes"
BRANCH="master"

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
uv run hexo-proc --verbose --git-batch=true --tag-method=textrank --tag-count=3 --tag-budget=100

# 生成静态文件
npm install
npm run clean
npm run build
