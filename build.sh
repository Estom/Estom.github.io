#!/usr/bin/env bash
# 在build阶段完成数据的处理，生成可部署的产物
set -euo pipefail

REPO_URL="git@gitee.com:Eyestorm/notes.git"
NOTES_DIR="notes"
BRANCH="master"

if [[ ! -d "$NOTES_DIR" ]]; then
	echo "[notes] $NOTES_DIR not found, cloning from $REPO_URL ..."
	git clone "$REPO_URL" "$NOTES_DIR"
else
	if [[ ! -d "$NOTES_DIR/.git" ]]; then
		echo "[notes] $NOTES_DIR exists but is not a git repository (.git missing)."
		echo "        Please move it away or remove it, then re-run."
		exit 2
	fi

	echo "[notes] updating $NOTES_DIR ($BRANCH) ..."
	git -C "$NOTES_DIR" fetch origin "$BRANCH"
	git -C "$NOTES_DIR" checkout "$BRANCH"
	git -C "$NOTES_DIR" pull --ff-only origin "$BRANCH"
fi

uv sync
uv run hexo-sync "$@"

npm install
npm run clean
npm run build