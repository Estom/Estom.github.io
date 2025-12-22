#!/usr/bin/env bash
# usage: ./remove-submodule.sh themes/xxx

SUBMODULE="$1"
[[ -z "$SUBMODULE" ]] && { echo "Usage: $0 <submodule-path>"; exit 1; }

# 1. 取消子模块注册并删除工作区
git submodule deinit -f "$SUBMODULE"
rm -rf "$SUBMODULE"

# 2. 删除 .git/modules 里的元数据
rm -rf .git/modules/"$SUBMODULE"

# 3. 清理 .gitmodules 条目
git config -f .gitmodules --remove-section submodule."$SUBMODULE" 2>/dev/null || true

# 4. 从暂存区移除（若已跟踪）
git rm -f "$SUBMODULE" 2>/dev/null || true

# 5. 提交变更
git add .gitmodules
git commit -m "chore: remove submodule $SUBMODULE"