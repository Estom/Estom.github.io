# Hexo Blog

这是一个基于 Hexo 的个人博客站点源码，使用 `butterfly` 主题（参考仓库：jerryc127/hexo-theme-butterfly）。仓库带有若干辅助脚本用于生成与同步文章。

**代办事项**

- [x] 数据处理相关
  - [x] 生成正确的时间戳。通过git。尝试优化时间戳的处理速度，不要单个文档去查询时间戳，而是查询一次所有文档的log，然后在内存中处理文档的时间戳。一次查询的历史长度太多了，导致内存爆炸。
  - [x] 引入文本分析功能，生成标签功能等关键部分。标签通过文本分析。提取到元信息头中。jieba分词和sklearn通过tfidf算法进行分词
  - [x] 自动添加封面图片。图片使用文章中的第一张图片，如果没有使用固定映射的图片，从images/cover中选取一张图片作为封面，已经准备了100张图片，按文件名哈希映射，防止不稳定的变化。提取到元信息头中。
  - [x] 增加进度条，显示文本处理的速度。
  - [x] ~~将数据处理部分直接按照hexo插件的形式开发。实现从远程仓库中下载文档，并完成数据处理的步骤。使用python专门的脚本~~
- [x] 个性化功能基础配置
  - [x] 阅读hexo官方的配置文档，完成部分个性化配置
  - [x] 阅读butterfly的配置文档，完成大部分配置。
  - [x] 阅读其他人建站的博客文章，完成全部的配置。
  - [x] 搜索功能。有点问题，引入了搜索插件，但是还是没有搜索功能
  - [x] 友情链接无法显示
  - [x] 关于页面没有内容
  - [x] 文章卡片上的图片为空。
  - [TODO] ~~评论系统。暂时不做~~
  - [TODO] ~~支持个人页和文章页的打赏功能。想的太早~~
- [ ] 自动化部署
  - [x] 完成构建脚本build.sh，从notes仓库中拉取文章，进行数据处理，并生成静态文件
  - [x] 完成部署脚本deploy.sh，将文章部署到github pages.
  - [x] 完成启动脚本start.sh，在本地启动hexo的静态文件服务器。
  - [x] 通过docker打包镜像。并发布到个人的镜像仓库中。
  - [ ] 使用github的gitactiongs功能进行自动化的部署。每次提交后重新打包镜像。推送到docker.hub镜像仓库和gitpages，完成部署
- [x] 风格指南
  - [x] 安静、动漫卡通的小镇日常。
  - [TODO] ~~绿色的自然凤凰。~~
  - [TODO] ~~赛博朋克~~
  - [TODO] ~~科幻、宇宙和星辰~~


CICI 流水线的过程
1. notes工程开发
2. build.sh构建脚本 / docker_build.sh 打包镜像到本地
3. deploy.sh将工程部署到github pages /docker_deploy.sh 推送镜像到镜像仓库
4. start.sh 启动当前的脚本。 /docker_run.sh 启动容器服务
**主要内容**

- 站点源码：根目录与 `source/`、`scaffolds/`、`public/` 等目录
- 主题：`themes/butterfly`
- 文章处理脚本：`processor/process_posts.py`, `processor/sync.py`
- 常用脚本：`start.sh`, `sync.sh`

**快速开始**

1. 安装依赖（确保已安装 Node.js、npm/ pnpm/yarn）:

```bash
npm install
# 或者使用 yarn / pnpm
```

2. 全局安装 hexo（如未安装）:

```bash
npm install -g hexo-cli
```

3. 本地调试：

```bash
# 清理并生成、启动本地预览
hexo clean
hexo g
hexo s
```

或者直接运行仓库自带脚本：

```bash
./start.sh
```

**目录概览**

- `source/_posts/`：博客文章源文件
- `themes/butterfly/`：Hexo Butterfly 主题（已包含或作为子模块）
- `processor/`：处理与同步文章的 Python 脚本
- `public/`：Hexo 生成的静态站点文件（可部署内容）

**部署**

生成后将 `public/` 目录内容上传或部署到你的静态站点托管服务（GitHub Pages、Netlify、Vercel、自托管服务器等）。

**贡献**

欢迎提交 issue 或 PR 来改进文章处理脚本、主题或站点配置。提交前请先在本地运行 `hexo g` 与 `hexo s` 验证无误。

**参考**

- 主题参考：jerryc127/hexo-theme-butterfly

---

若需我把 `themes/butterfly` 与上游同步、或补充站点部署说明（如 GitHub Actions 部署配置），我可以继续帮你生成对应文件与说明。