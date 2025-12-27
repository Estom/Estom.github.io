# Quick Hexo Blog

本项目用于快速搭建个人的博客网站。将现有的markdown笔记仓库，快速转换为可以开箱可用的个人博客。

基于 Hexo 的个人博客框架，主题使用 `butterfly`（来自 `hexo-theme-butterfly`），通过 **Python数据处理模块**，从个人笔记仓库同步 Markdown 和图片，并自动补齐 front-matter、提取标签、修正图片路径、生成封面，并最终由 Hexo 产出 `public/` 静态站点，已经提供了butterfly、hexo的基础配置，开箱急用。


## 目录与职责

- `notes/`：外部笔记仓库。
- `processor/`：Python 数据处理（通过 `uv` 安装与运行）。
  - `hexo-sync`：同步 `notes/` 到 Hexo（Markdown + 图片），并触发后处理。
  - `hexo-proc`：仅对 `source/_posts/` 做统一后处理。生成 front-matter.
- `source/_posts/`：Hexo 文章输入目录（由 `hexo-sync` 写入）。
- `source/note_image/`：从 `notes/` 同步过来的图片目录（保留原目录结构）。
- `source/images/cover/`：封面素材目录（默认会从 100 张图片中按 hash 稳定选取）。
- `public/`：Hexo 输出静态站点（构建产物）。
- `_config.yml`：Hexo 主配置（含 deploy 配置与 `hexo-generator-searchdb` 的配置）。
- `_config.butterfly.yml`：Butterfly 主题配置（已启用 `local_search`）。

## 环境要求

主要的工作流程：从 notes 同步数据 -> Python 后处理 -> Hexo 构建。依赖如下环境：
- `Node.js` >= 22.x
- `Python` >= 3.10
- `uv`
- `git`


## 快速开始

1. 复制.env.example 为 .env，配置个人笔记仓库的地址`NOTE_REPO_URL`。

```sh
# 你的markdown笔记仓库。保证仓库是公开仓库
NOTE_REPO_URL=
# 需要同步的markdown笔记仓库的分支，默认为master
NOTE_REPO_BRANCH=master

# 标签生成方法，可选项：tfidf,textrank,keybert。默认为textrank，平衡提取效果和性能
TAG_METHOD=textrank

# 如果使用keybert方法生成标签，由于国内访问Hugging Face模型较慢，可以配置镜像地址
HF_ENDPOINT=https://hf-mirror.com
```
2. 执行构建脚本
```bash
./build.sh
```

构建完成后，静态站点位于 `public/`。

3. 本地预览。用 Hexo 自带 server（端口 4000，或你自己指定）

```bash
npm run server
```

4. 访问查看网页。
```
http://localhost:4000
```

## 功能说明

### 构建过程

[build.sh](build.sh) 内部会运行：

1. 通过`git clone / git pull` 同步笔记到本地，存储到 `notes/` 中，保持最新
2. `uv sync` 安装数据处理的依赖
3. `uv run hexo-sync` 进行数据同步，将笔记同步到hexo的数据目录中`/source/_posts/`
4. `uv run hexo-proc` 进行数据处理，处理并生成笔记中的 `front-matter`（标签、封面、时间戳等）
5. `npm install && npm run clean && npm run build` 通过hexo生成静态站点。



### hexo-sync数据同步

#### `hexo-sync` 的功能说明：

`hexo-sync` 的默认行为（见 [processor/sync.py](processor/sync.py)）：

- 扫描 `notes/` 下所有 Markdown 与图片文件
- 应用忽略规则文件（默认 [ .bgignore ](.bgignore)）
- 将满足"目录子树 Markdown 数量阈值"的 Markdown 复制到 `source/_posts/`（默认阈值：2）
- 将所有图片复制到 `source/note_image/`（不受阈值影响，以免相对引用断掉）


#### `hexo-sync` 的可用参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--repo-root` | 当前目录 | 指定仓库根目录 |
| `--notes` | `{repo_root}/notes` | 指定 notes 目录路径 |
| `--target` | `source/_posts` | 指定 Markdown 文件的目标目录 |
| `--image-target` | `source/note_image` | 指定图片文件的目标目录 |
| `--ignore` | `{repo_root}/.bgignore` | 指定忽略规则文件 |
| `--min-md` | `2` | 目录子树 Markdown 数量阈值 |
| `--dry-run` | false | 只显示将要复制的文件，不实际执行 |
| `--delete` | false | 同步前删除目标目录中的已有文件 |
| `--no-post-process` | false | 不执行后处理步骤 |
| `--verbose` | false | 显示详细处理过程 |


#### 常用参数组合：

```bash
# 只看会复制哪些文件（不落盘）
uv run hexo-sync --dry-run

# 同步前清空既有文章/图片（适合做一次"全量重建"）
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

你可以按需要扩展该文件，控制哪些笔记目录会被同步进 Hexo。

### hexo-proc内容处理

#### hexo-proc功能说明 
[processor/sync.py](processor/sync.py)

数据同步完成后执行数据处理步骤
```bash
uv run hexo-proc
```

1. 将文章中图片的相对路径转换为基于note_images的绝对路径
2. 生成front-matter，提供给hexo博客生成系统。
   1. 基于git的提交记录生成生成提交和更新时间戳。
   2. 通过tfidf、textrank、keybert等方法生成文章的标签关键词。
   3. 使用文章中的第一张图片作为封面图片，如果没有图片则使用images/cover目录下内置的风景图片作为封面。根据哈希映射固定的风景图片。


#### hexo-proc 参数详解

`hexo-proc` 的最小参数配置：
- `--target`：必须指定要处理的文章目录（通常是 `source/_posts`）

`hexo-proc` 的可用参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--target` | 无（必填） | 指定要处理的文章目录 |
| `--notes` | `{target}/../notes` | 指定 notes 目录路径 |
| `--tag-count` | `5` | 每篇文章提取的标签数量 |
| `--tag-budget` | `100` | 全局唯一标签总量上限 |
| `--image-root` | `/note_image` | 图片 URL 根路径 |
| `--cover-dir` | `source/images/cover` | 封面图片目录 |
| `--cover-count` | `1` | 每篇文章使用的封面图片数量 |
| `--raw-wrap` | `auto` | 遇到模板语法时用 Nunjucks raw 包裹正文（auto/always/never） |
| `--escape-curly` | `true` | 是否转义 {{ }} |
| `--git-date` | `author` | 时间戳读取使用 author/committer |
| `--git-batch` | `true` | 是否批量读取 git 时间戳 |
| `--force-regen` | `false` | 强制重新生成 front-matter |
| `--verbose` | `false` | 显示详细处理过程 |

#### 常用参数组合

```bash
# 每篇文章提取 3 个标签；全局唯一标签总量最多 100
uv run hexo-proc --target source/_posts --tag-count 3 --tag-budget 100

# 图片 URL 根路径（默认 /note_image）
uv run hexo-proc --target source/_posts --image-root /note_image

# 遇到模板语法时用 Nunjucks raw 包裹正文：auto/always/never
uv run hexo-proc --target source/_posts --raw-wrap auto

# 转义 {{ }}（默认 true）
uv run hexo-proc --target source/_posts --escape-curly true

# 时间戳读取使用 author/committer（默认 author）
uv run hexo-proc --target source/_posts --git-date author
```

重要说明：

- `hexo-proc` **要求** `notes/` 是一个 git 仓库（需要 `notes/.git`），否则无法生成时间戳。

## Docker镜像构建
Docker镜像构建 分为两个步骤：

- [Dockerfile-base](Dockerfile-base)：基础镜像（Ubuntu 24.04 + Node.js 22 + Python 3 + uv，含国内镜像源配置）,搭建基础的构建环境。基础镜像可以重复利用，加快构建的过程。
- [Dockerfile](Dockerfile)：分层构建镜像，首先复制仓库并执行 `./build.sh`，产出 `/app/public`）。然后使用ngix构建运行镜像，拷贝 `/app/public` 并以 [start.sh](start.sh) 启动。封层构建降低最终运行镜像的大小。

如果你只想本地快速跑一个静态站点容器，推荐直接构建运行镜像：

```bash
docker build -t hexo-blog:base-v1.0.0 -f Dockerfile-base .
docker build -t hexo-blog:run-v1.0.0 -f Dockerfile .
docker run --rm -p 8080:80 hexo-blog:run-v1.0.0
```

浏览器打开：`http://localhost:8080`。

仓库内脚本：

- [docker-build.sh](docker-build.sh) 是一个示例构建脚本
- [docker-run.sh](docker-run.sh) ，如果你本地镜像不是这个名字，需要自行调整

## GitHub Actions自动构建部署
通过GitHub Actions：构建镜像，并发布到github的Pages和cloudflare的Pages。推送main分支时，会触发自动构建和部署。

工作流见 [.github/workflows/build-and-deploy.yml](.github/workflows/build-and-deploy.yml)。构建并推送镜像（base/run）到镜像仓库（默认 GHCR），然后部署到github pages和cloudflare pages。


关键点：

- 版本号从仓库文件 `vsersion` 读取（注意文件名就是 `vsersion`）。如果笔记仓库有更新，可以新增版本号并推送。则会重新触发流水线拉取最新的分支，并部署。


[必选] 必须配置一下secrets变量`（github仓库->设置->Secrets and variables->Actions -> Secrets ->Repository secrets）`，流水线才能正常执行:

- `REGISTRY_PASSWORD`：ghcr镜像仓库的token
- `REGISTRY_USERNAME`：ghcr镜像仓库的用户名
- `REPO_URL`: 笔记仓库的URL


[可选] 如果已经构建过基础镜像，可以重复利用之前构建好的基础镜像。则需要配置github actions的vars变量`（github仓库->设置->Secrets and variables->Actions -> Varibles ->Repository varibles）`
```
SKIP_BASE_IMAGE: true
BASE_IMAGE_REF: ghcr.io/your-username/hexo-blog:base-v1.0.0
```

[可选] 如果想要同步发布的cloudfalre pages，需要配置如下secrets变量`（github仓库->设置->Secrets and variables->Actions -> Secrets ->Repository secrets）`:
- `CLOUDFLARE_ACCOUNT_ID`: cloudflare 的账户id
- `CLOUDFLARE_API_TOKEN`: cloudflare上的api token
- `CLOUDFLARE_PAGES_PROJECT_NAME`: cloudflare pages的project name

## 常见问题

### 1 hexo-sync 同步了图片但文章里的相对图片路径不显示

后处理会把相对图片路径重写到 `--image-root`（默认 `/note_image`）下，并保持目录结构。确认：

- 图片确实被复制到了 `source/note_image/...`
- Hexo 生成后 `public/note_image/...` 存在

### 2 报错：notes 仓库不存在或不是 git 仓库

这是 `hexo-proc` 的硬性要求（需要 git 历史生成时间戳）。解决方式：

- 让 `notes/` 保持为 git 仓库（推荐用 [build.sh](build.sh) 自动 clone/pull）
- 或者跳过后处理

### 3 搜索框存在但搜不到

当前主题配置已启用本地搜索（见 [_config.butterfly.yml](./_config.butterfly.yml) 的 `search.use: local_search`）。如果仍然不生效，请确认：

- 依赖已安装：`hexo-generator-searchdb`（见 [package.json](package.json)）
- Hexo 配置里已启用 searchdb 生成（见 [_config.yml](./_config.yml) 的 `search:` 段）
- 生成产物中存在 `public/search.xml`

## 安全提示

仓库里包含 `notes/` 的内容（可能来自外部同步）。在提交/公开仓库前，务必检查是否意外包含敏感信息（例如凭据、密码、token 等）。
