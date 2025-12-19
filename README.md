# Hexo Blog

这是一个基于 Hexo 的个人博客站点源码，使用 `butterfly` 主题（参考仓库：jerryc127/hexo-theme-butterfly）。仓库带有若干辅助脚本用于生成与同步文章。

**代办事项**

- [ ] 数据处理相关
  - [x] 生成正确的时间戳。通过git。尝试优化时间戳的处理速度，不要单个文档去查询时间戳，而是查询一次所有文档的log，然后在内存中处理文档的时间戳。一次查询的历史长度太多了，导致内存爆炸。
  - [ ] ~~引入文本分析数据库，生成标签、摘要等关键部分。等以后再说~~
  - [x] 增加进度条，显示文本处理的速度。
  - [ ] ~~将数据处理部分直接按照hexo插件的形式开发。实现从远程仓库中下载文档，并完成数据处理的步骤。~~
- [ ] 个性化配置相关
  - [x] 阅读hexo官方的配置文档，完成部分个性化配置
  - [ ] 阅读butterfly的配置文档，完成大部分配置。
  - [ ] 阅读其他人建站的博客文章，完成全部的配置。
- [ ] 自动化部署
  - [ ] 优化启动脚本。启动一个定时任务，每天凌晨两点检测notes仓库是否有更新。如果有更新，则拉取最新的更新，并重新执行部署和重启的脚本。

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