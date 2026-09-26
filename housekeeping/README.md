# housekeeping

GitHub 账号整理：清理过时仓库、给 star 分组。两件事都在本地用 [GitHub CLI](https://cli.github.com)（`brew install gh`，然后 `gh auth login`）手动执行，默认只预览。

## 仓库清理

2026-09-26 盘点了全部 67 个仓库，逐个看了提交历史和作者、fork 相对上游多出的提交，以及博客内容对这些仓库的引用。公开仓库的结论写在 [repos.tsv](repos.tsv)，每行都附了理由；私有仓库的结论不放在这个公开仓库里。

| 处理 | 数量 | 包括 |
|---|---|---|
| 删除 | 33 | 没有自己提交的 fork，改动已经合入上游的 fork，空仓库和模板，已被别的仓库取代的旧项目 |
| 归档 | 11 | 有自己的代码或内容、但不再维护的项目：只读，链接、raw 图片和 `go get` 照常可用 |
| 转私有并归档 | 1 | Notes（旧 Obsidian 库） |
| 保留 | 12 | 在用的，或者被别的东西依赖的 |

执行完后，公开仓库从 57 个减到 23 个：12 个在用，11 个已归档。

### 删之前要知道的依赖

- **pic-sync 不能删**：11 篇博文里的 37 张图片还从 `raw.githubusercontent.com/whrsss/pic-sync/...` 加载。
  这些链接用的是旧用户名 `whrsss`，靠 GitHub 的改名重定向才能打开。如果有人注册了 `whrsss` 并建一个同名仓库，重定向就会失效，图片也可能被对方替换。建议把链接改成 `whrss9527/pic-sync`，或者把图片迁到 `pic.whrss.com`。
- **blog-comments 不能删**：giscus 评论存在它的 Discussions 里。
- **blog-backup**：`mysql-sharding-migration.md` 末尾还链接着它，删之前先把链接去掉。
- **go-retryablehttp 保留**：这个 fork 里有 5 个上游没有的提交（带 context 的日志），而且到 2025-08 还在同步上游，很可能有项目通过 `replace` 在用。
- **edgetunnel、GPT-Web**：如果 Cloudflare 或 Vercel 上还挂着从它们部署的站点，先确认是否还用；不用的话，把平台上的项目一起删掉。

### 执行

```bash
cd housekeeping
bash repos.sh                                   # 预览：实时查 star / fork 数，删除项有人 star 或 fork 会标 ⚠
gh auth refresh -h github.com -s delete_repo    # 删除仓库需要这个权限
bash repos.sh --apply                           # 执行，开始前会再确认一次
```

- 想改某个决定，直接改 `repos.tsv` 那一行的第一列：`delete`、`archive`、`private`、`private+archive` 或 `keep`。
- 私有仓库也要处理的话，按同样的格式写进 `repos.private.tsv`（已加入 .gitignore），脚本会一起读取。
- 中途失败或中断了可以直接重跑，已经处理过的会跳过。
- 归档随时可以在仓库 Settings 里撤销。删除的非 fork 仓库，一般 90 天内还能在 Settings → Repositories → Deleted repositories 恢复；fork 基本恢复不了。

## star 分组

[stars.py](stars.py) 按 [star-lists.json](star-lists.json) 里的规则，把 star 分进 GitHub 的 Lists（Stars 页面里的分组）。

```bash
cd housekeeping
python3 stars.py export              # 拉取全部 star，存到 stars.json（不入库）
python3 stars.py plan                # 预览分组，不做任何修改
python3 stars.py plan --unmatched    # 只看规则没覆盖到的仓库
python3 stars.py apply               # 创建缺少的 List 并归类
```

预设的分组：

| List | 放什么 |
|---|---|
| 🤖 AI 与大模型 | LLM 应用、Agent、MCP、提示词与各类 AI 工具 |
| 🌐 网络与代理 | 代理、隧道、DNS、内网穿透与分流规则 |
| 🏗️ 后端与架构 | 数据库、缓存、消息队列、RPC、微服务、分布式与系统设计 |
| ☁️ 云原生与运维 | 容器、K8s、CI/CD、监控可观测、部署与自托管 |
| 🧰 效率工具 | 命令行、终端、编辑器、桌面应用与各类效率工具 |
| 📝 博客与内容 | 博客程序与主题、RSS、评论系统、个人主页与阅读 |
| 📚 学习资料 | 教程、书籍、面试、算法、Awesome 清单与路线图 |
| 🎨 前端与设计 | 前端框架、UI 组件、CSS、图标字体与可视化 |
| 📱 移动与客户端 | Android、iOS、鸿蒙、Flutter、小程序与桌面客户端 |
| 🏃 生活与数据 | 运动健康、个人数据可视化、记账理财与生活 |
| 🎮 游戏开发 | 游戏服务端、引擎与相关工具 |
| 🐹 Go 生态 | 没进上面分类的 Go 框架、库与工具 |
| ☕ Java / Kotlin | 没进上面分类的 JVM 生态项目 |
| 🗂️ 其他 | 规则没覆盖到的 |

怎么分：

- 每个仓库对每个 List 打分：topic 命中 +3，关键词出现在仓库名 +2、只出现在描述 +1，主语言命中 +2。
- 仓库进得分最高的那个 List，同分时 star-lists.json 里靠前的优先；得分低于 `min_score` 的进「🗂️ 其他」。
- 分错的仓库在 `overrides` 里手动指定，比如 `"spf13/cobra": ["🐹 Go 生态"]`。

`apply` 的行为：

- 只创建至少分到一个仓库的 List。
- 只增不减：已有的 List，以及你手动做的分组都会保留。
- 每次修改间隔 1 秒；遇到 GitHub 限流会自动等待重试。中断后直接重跑，已经分好的会跳过。
