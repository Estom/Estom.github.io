# Hexo Blog（Hexo + Butterfly + notes 同步）

这是一个基于 Hexo 的个人博客站点源码，主题使用 `butterfly`（来自 `hexo-theme-butterfly`），并额外提供一套 **Python 处理流水线**：从 `notes/` 仓库同步 Markdown 和图片、自动补齐 front-matter、提取标签、修正图片路径、生成封面，并最终由 Hexo 产出 `public/` 静态站点。

本 README 以“能跑起来”为第一原则：所有命令与参数均来自仓库实际脚本实现。

## 目录与职责

- `notes/`：外部笔记仓库（默认从 `https://gitee.com/Eyestorm/notes.git` 克隆/更新）。
- `processor/`：Python 处理器（通过 `uv` 安装与运行）。
  - `hexo-sync`：同步 `notes/` 到 Hexo（Markdown + 图片），并触发后处理。
  - `hexo-process-posts`：仅对 `source/_posts/` 做统一后处理。
  - `hexo-rename-covers`：批量重命名封面素材图片。
- `source/_posts/`：Hexo 文章输入目录（由 `hexo-sync` 写入）。
- `source/note_image/`：从 `notes/` 同步过来的图片目录（保留原目录结构）。
- `source/images/cover/`：封面素材目录（默认会从 100 张图片中按 hash 稳定选取）。
- `public/`：Hexo 输出静态站点（构建产物）。
- `_config.yml`：Hexo 主配置（含 deploy 配置与 `hexo-generator-searchdb` 的配置）。
- `_config.butterfly.yml`：Butterfly 主题配置（已启用 `local_search`）。

## 环境要求

主要的工作流程：从 notes 同步数据 -> Python 后处理 -> Hexo 构建。依赖如下环境：
- Node.js + npm
- Python >= 3.10
- `uv`（用于安装/运行 `processor/`）
- git（用于拉取 notes、读取 git 历史生成时间戳）

说明：`processor/` 的依赖来自 [pyproject.toml](pyproject.toml) ，核心库包含 `jieba`、`scikit-learn`、`pathspec`。

## 快速开始（推荐：完整流水线）

### 1. 一键构建

```bash
./build.sh
```

拉取 notes → 同步/后处理 → Hexo generate

构建完成后，静态站点位于 `public/`。

### 2. 本地预览

用 Hexo 自带 server（端口 4000，或你自己指定）

```bash
npm run server
```

## 本地运行

### 从 notes 同步文章（核心命令：hexo-sync）

[build.sh](build.sh) 内部会运行：

1) 确保 `notes/` 存在且尽量保持最新（git clone / git pull）
2) `uv sync`
3) `uv run hexo-sync ...`
4) `npm install && npm run clean && npm run build`

你也可以手动运行：

```bash
uv sync
uv run hexo-sync
```

查看帮助：

```bash
uv run hexo-sync --help
```

#### hexo-sync 行为说明

`hexo-sync` 的默认行为（见 [processor/sync.py](processor/sync.py)）：

- 扫描 `notes/` 下所有 Markdown 与图片文件
- 应用忽略规则文件（默认 [ .bgignore ](.bgignore)）
- 将满足“目录子树 Markdown 数量阈值”的 Markdown 复制到 `source/_posts/`（默认阈值：2）
- 将所有图片复制到 `source/note_image/`（不受阈值影响，以免相对引用断掉）
- 同步完成后，默认会执行后处理：调用 `processor.process_posts` 扫描 `source/_posts/`，统一生成 front-matter、标签、封面、时间戳等

常用参数：

```bash
# 只看会复制哪些文件（不落盘）
uv run hexo-sync --dry-run

# 同步前清空既有文章/图片（适合做一次“全量重建”）
uv run hexo-sync --delete

# 修改目录子树阈值（默认 2）
uv run hexo-sync --min-md 1

# 指定 notes 目录（默认 repo_root/notes）
uv run hexo-sync --notes /abs/path/to/notes

# 跳过后处理（只做复制）
uv run hexo-sync --no-post-process
```

#### .bgignore 规则

[.bgignore](.bgignore) 采用 gitignore 风格的匹配规则（由 `pathspec` 解析）。当前默认忽略：

- `blog`
- 以 `_` 开头的目录/文件（`_*`）
- `.git`
- `*.pdf`

你可以按需要扩展该文件，控制哪些笔记目录会被同步进 Hexo。

### hexo-process-posts对现有文章做后处理

如果你已经有了 `source/_posts/`（不一定来自 `notes/`），可以单独跑后处理：

```bash
uv sync
uv run hexo-process-posts --target source/_posts
```

常用参数（见 [processor/process_posts.py](processor/process_posts.py)）：

```bash
# 每篇文章提取 3 个标签；全局唯一标签总量最多 100
uv run hexo-process-posts --tag-count 3 --tag-budget 100

# 图片 URL 根路径（默认 /note_image）
uv run hexo-process-posts --image-root /note_image

# 遇到模板语法时用 Nunjucks raw 包裹正文：auto/always/never
uv run hexo-process-posts --raw-wrap auto

# 转义 {{ }}（默认 true）
uv run hexo-process-posts --escape-curly true

# 时间戳读取使用 author/committer（默认 author）
uv run hexo-process-posts --git-date author
```

重要说明：

- `hexo-process-posts` **要求** `notes/` 是一个 git 仓库（需要 `notes/.git`），否则会报错。
- 参数 `--git-batch` 的代码默认值是 `false`。


## Docker
构建镜像 + 运行

本仓库的 Docker 分为三层：

- [Dockerfile-base](Dockerfile-base)：基础镜像（Ubuntu 24.04 + Node.js 22 + Python 3 + uv，含国内镜像源配置）
- [Dockerfile-build](Dockerfile-build)：构建镜像（复制仓库并执行 `./build.sh`，产出 `/app/public`）
- [Dockerfile](Dockerfile)：运行镜像（nginx，拷贝 `/app/public` 并以 [start.sh](start.sh) 启动）

如果你只想本地快速跑一个静态站点容器，推荐直接构建运行镜像：

```bash
docker build -t hexo-blog:run .
docker run --rm -p 8080:80 hexo-blog:run
```

浏览器打开：`http://localhost:8080`。

仓库内脚本：

- [docker-build.sh](docker-build.sh) 是一个示例构建脚本
- [docker-run.sh](docker-run.sh) ，如果你本地镜像不是这个名字，需要自行调整

## CI/CD
GitHub Actions：构建镜像 + 发布 Pages

工作流见 [.github/workflows/build-and-deploy.yml](.github/workflows/build-and-deploy.yml)。核心逻辑：

1) 构建并推送三类镜像（base/build/run）到镜像仓库（默认 GHCR）
2) 使用 build 镜像作为 runner 容器环境，运行 [deploy.sh](deploy.sh) 发布 GitHub Pages

关键点：

- 版本号从仓库文件 `vsersion` 读取（注意文件名就是 `vsersion`）
- Pages 发布需要 `PAGES_REPO_TOKEN`（PAT），用于向 `PAGES_REPO` 指定的 Pages 仓库推送

`deploy.sh` 的行为：

- 本地：直接 `npm run deploy`（走 `_config.yml` 里的 SSH repo 配置）
- GitHub Actions：生成 `_config.ci.deploy.yml`，使用 HTTPS + token 推送，避免依赖 SSH key

可用环境变量（CI 下）：

- `PAGES_REPO_TOKEN`：必填（推荐使用 GitHub Secret）
- `PAGES_REPO`：默认 `Estom/Estom.github.io`
- `PAGES_BRANCH`：默认 `main`

## 常见问题（排错）

### 1) hexo-sync 同步了图片但文章里的相对图片路径不显示

后处理会把相对图片路径重写到 `--image-root`（默认 `/note_image`）下，并保持目录结构。确认：

- 图片确实被复制到了 `source/note_image/...`
- Hexo 生成后 `public/note_image/...` 存在

### 2) 报错：notes 仓库不存在或不是 git 仓库

这是 `hexo-process-posts` 的硬性要求（需要 git 历史生成时间戳）。解决方式：

- 让 `notes/` 保持为 git 仓库（推荐用 [build.sh](build.sh) 自动 clone/pull）
- 或者跳过后处理：`uv run hexo-sync --no-post-process`

### 3) CI 部署报错：Missing token

说明 `PAGES_REPO_TOKEN` 未配置或无权限。需要一个对目标 Pages 仓库有 `Contents: Read & Write` 权限的 PAT。

### 4) 搜索框存在但搜不到

当前主题配置已启用本地搜索（见 [_config.butterfly.yml](./_config.butterfly.yml) 的 `search.use: local_search`）。如果仍然不生效，请确认：

- 依赖已安装：`hexo-generator-searchdb`（见 [package.json](package.json)）
- Hexo 配置里已启用 searchdb 生成（见 [_config.yml](./_config.yml) 的 `search:` 段）
- 生成产物中存在 `public/search.xml`

## 安全提示

仓库里包含 `notes/` 的内容（可能来自外部同步）。在提交/公开仓库前，务必检查是否意外包含敏感信息（例如凭据、密码、token 等）。

---

如果你希望我再补一版“面向作者写作”的说明（比如 notes 仓库目录组织规范、哪些目录会被同步、图片引用的最佳写法），告诉我你期望的 notes 目录规则，我可以按你现有笔记结构把约定写成更明确的规范。