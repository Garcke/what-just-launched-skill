# What Just Launched Skill

`what-just-launched` 是一个用于 Codex 的新产品发现 skill。它的目标不是泛泛地做市场调研，而是回答一个更具体的问题：

```text
最近刚上线了什么值得关注的新产品？
```

它会从产品发布平台、应用商店、开发者社区、网页搜索和用户反馈源中收集信号，输出结构化结果，帮助 Codex 进一步整理成中文产品简报。

## 适合做什么

- 发现最近 7 天 / 30 天新上线的 AI 产品、App、SaaS、开发者工具、开源项目。
- 追踪某个方向最近有什么新产品，例如 AI Agent、AI 视频工具、移动 App、开发者工具。
- 检查新产品是否有早期热度信号，例如 HN points、GitHub stars、App Store 评分、网页讨论。
- 收集产品发布后的用户反馈，例如 Reddit、X/Twitter、YouTube、Hacker News、网页评论与评测。
- 生成「最近新产品列表」「值得关注的新产品」「某品类产品机会」这类 briefing。

## Skill 位置

```text
skills/what-just-launched
```

核心脚本：

```text
skills/what-just-launched/scripts/just-launched.py
```

脚本入口保持很薄，实际实现拆在 Python 包里：

```text
skills/what-just-launched/scripts/just_launched/
├── cli.py        # CLI 参数、配置写入、JSON 输出
├── engine.py     # 搜索引擎编排和数据源 adapter
├── ranking.py    # 去重、归一化评分、加权 RRF 融合
└── __init__.py
```

## 数据源

### 产品发现源

第一版设计的产品发现源：

| 来源 | 用途 | 访问方式 |
|---|---|---|
| Product Hunt | SaaS、AI 工具、独立产品、发布榜 | 需要 `PRODUCT_HUNT_TOKEN` |
| AppPark | App Store / Google Play 风格榜单和分类榜 | 公共接口，浏览器 User-Agent |
| Hacker News | Show HN、Launch HN、开发者产品 | HN Algolia API |
| GitHub Trending / Search | 开源项目、开发者工具、新仓库 | GitHub 页面/API |
| Apple RSS / iTunes Search | iOS App 榜单和元数据 | Apple 公共 API |
| Google Play / AppBrain | Android App 发现补充 | AppBrain 页面搜索 |
| BetaList | 早期 startup / waitlist 产品 | 公共页面，低频访问 |
| AI 工具目录 | AI 产品目录和垂直工具 | 公共页面，低频访问 |

### 用户反馈源

| 来源 | 用途 | 访问方式 |
|---|---|---|
| Reddit | 真实用户讨论、抱怨、对比 | OAuth 优先，默认不抓 HTML |
| X / Twitter | 发布反应、创始人/用户讨论 | `XQUIK_API_KEY` 或外部 adapter |
| YouTube | 测评视频、教程、评论 | `YOUTUBE_API_KEY` |
| Hacker News | 开发者反馈和质疑 | HN Algolia API |
| Web Search | 官网、评测、榜单、对比文章 | Tavily / Brave / Exa / Serper / DuckDuckGo |

## 安装到 Codex

如果你是从 GitHub 克隆这个仓库，可以把 skill 目录复制到 Codex skills 目录：

```bash
git clone https://github.com/Garcke/what-just-launched-skill.git
mkdir -p ~/.codex/skills
cp -R what-just-launched-skill/skills/what-just-launched ~/.codex/skills/
```

Windows PowerShell 示例：

```powershell
git clone https://github.com/Garcke/what-just-launched-skill.git
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills"
Copy-Item -Recurse -Force "what-just-launched-skill\skills\what-just-launched" "$env:USERPROFILE\.codex\skills\"
```

## 安装到其他 Agent 工具

这个仓库使用的是通用 Agent Skills 结构：

```text
skills/what-just-launched/SKILL.md
skills/what-just-launched/scripts/just-launched.py
skills/what-just-launched/scripts/just_launched/
skills/what-just-launched/references/
```

大多数支持 Agent Skills 的工具都能读取这种「一个 skill 文件夹 + `SKILL.md` + scripts/references」结构。不同工具的差异主要是 skill 目录位置和是否需要额外 allowlist。

### Claude Code

Claude Code 官方支持 skills。通常可以把 skill 复制到 Claude 的 skills 目录：

```bash
mkdir -p ~/.claude/skills
cp -R skills/what-just-launched ~/.claude/skills/
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills"
Copy-Item -Recurse -Force "skills\what-just-launched" "$env:USERPROFILE\.claude\skills\"
```

然后在 Claude Code 中直接提问：

```text
Use what-just-launched to find new AI products from the last 7 days.
```

如果你不确定 Claude 是否已经发现该 skill，可以重启 Claude Code，或打开 `/skills` / slash command 相关界面检查。

参考：Claude Code 官方文档的 skills 说明：<https://code.claude.com/docs/en/skills>

### Kimi Code CLI

Kimi Code CLI 支持 Agent Skills。可以优先使用共享 `.agents/skills/` 目录：

```bash
mkdir -p .agents/skills
cp -R skills/what-just-launched .agents/skills/
```

如果你想全局使用，可以放到用户级目录，具体位置以 Kimi Code CLI 当前文档为准。常见方式是让当前项目包含：

```text
.agents/skills/what-just-launched/SKILL.md
```

然后在 Kimi Code 中请求：

```text
Use what-just-launched to discover new mobile apps launched this week.
```

参考：Kimi Code CLI Agent Skills 文档：<https://moonshotai.github.io/kimi-cli/en/customization/skills.html>

### Cursor

Cursor 支持 Agent Skills，可以通过项目级或个人级 skills 目录让 Agent 自动发现。优先推荐项目级安装，这样团队成员克隆项目后也能看到同一套 skill。

项目级安装：

```bash
mkdir -p .cursor/skills
cp -R skills/what-just-launched .cursor/skills/
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force -Path ".cursor\skills"
Copy-Item -Recurse -Force "skills\what-just-launched" ".cursor\skills\"
```

个人级安装可以放到你的 Cursor 用户配置目录，具体路径以 Cursor 当前版本为准。安装后在 Cursor Agent Chat 中直接请求：

```text
Use what-just-launched to find new AI agent products launched in the last 7 days.
```

Cursor 会根据 `SKILL.md` frontmatter 里的 `description` 判断是否需要加载该 skill。若没有自动触发，可以显式说 `use what-just-launched skill`。

参考：Cursor Agent Skills 文档：<https://cursor.com/docs/skills>

### OpenCode

OpenCode 官方支持 Agent Skills，会从 repo 或 home 目录发现 `SKILL.md` 定义，并通过内置 skill tool 按需加载。项目级安装推荐放在 `.agents/skills/`：

```bash
mkdir -p .agents/skills
cp -R skills/what-just-launched .agents/skills/
```

也可以放在用户级技能目录，具体路径以你的 OpenCode 配置为准。项目里可以增加一条提示，让 OpenCode 更容易选择它：

```text
When the task is about finding recently launched products, use .agents/skills/what-just-launched.
```

然后在 OpenCode 里请求：

```text
Use the what-just-launched skill to list new AI products launched this week.
```

参考：OpenCode Agent Skills 文档：<https://opencode.ai/docs/skills/>

### OpenClaw

OpenClaw 支持 skills 配置和 allowlist。建议先把 skill 放到 OpenClaw 能扫描的 skills 目录，然后在 OpenClaw 的 skills config 中允许 `what-just-launched`。

示例目录结构：

```text
~/.openclaw/skills/what-just-launched/SKILL.md
```

复制示例：

```bash
mkdir -p ~/.openclaw/skills
cp -R skills/what-just-launched ~/.openclaw/skills/
```

如果你的 OpenClaw 实例使用 allowlist，请把 `what-just-launched` 加进去。OpenClaw 文档强调 allowlist 是可见性和加载过滤，不是 shell 权限边界，所以仍然要认真检查第三方 skill 代码。

参考：OpenClaw skills config 文档：<https://docs.openclaw.ai/tools/skills-config>

### Hermes Agent

Hermes Agent 更偏「自学习 agent + profile/workspace 配置」模式。建议把本 skill 放进 Hermes 当前 workspace 的 skills 目录，或放到你自己的 agent resources 目录，然后在 Hermes 的项目说明或 profile 中明确引用。

推荐结构：

```text
<your-hermes-workspace>/skills/what-just-launched/SKILL.md
```

示例说明可以写进 Hermes workspace/profile：

```text
When asked to discover recently launched products, use the skill at skills/what-just-launched.
Run scripts/just-launched.py for structured launch search results.
```

参考：Hermes Agent 文档：<https://hermes-agent.nousresearch.com/docs/>

### 通用 Agent Skills 目录

一些工具使用共享目录：

```text
.agents/skills/
```

如果你的 agent 支持该约定，可以直接复制：

```bash
mkdir -p .agents/skills
cp -R skills/what-just-launched .agents/skills/
```

这种方式适合 Kimi Code、部分 IDE agent、云端 coding agent 或支持开放 Agent Skills 结构的工具。若工具没有自动发现，可以在项目说明文件中显式写：

```text
Use .agents/skills/what-just-launched when the task is about discovering recently launched products.
```

### 手动命令方式

如果某个 agent 工具暂时不支持 skills，你仍然可以把它当作普通 CLI 工具使用：

```bash
cd skills/what-just-launched
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

然后把 JSON 输出交给该 agent 总结。这个方式最通用，也最容易调试。

## 快速开始

进入 skill 目录：

```bash
cd skills/what-just-launched
```

查最近 7 天新 AI 产品：

```bash
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

查最近 30 天新移动 App：

```bash
python scripts/just-launched.py "new mobile apps" --mode discovery --days 30 --market us
```

使用明确时间范围，并要求按产品上线日期过滤：

```bash
python scripts/just-launched.py "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

查某个产品的用户反馈：

```bash
python scripts/just-launched.py "Cursor AI reviews" --mode feedback --days 30 --sources web,hacker_news
```

检查哪些数据源可用：

```bash
python scripts/just-launched.py --preflight
```

输出更完整的诊断信息：

```bash
python scripts/just-launched.py --diagnose
```

## 常用参数

| 参数 | 说明 |
|---|---|
| `query` | 搜索关键词，例如 `"new AI products"` |
| `--mode discovery` | 发现新产品 |
| `--mode feedback` | 收集用户反馈 |
| `--mode all` | 同时发现产品和反馈 |
| `--days 7` | 最近 7 天 |
| `--since YYYY-MM-DD` | 开始日期 |
| `--until YYYY-MM-DD` | 结束日期 |
| `--filter-launch-date` | 只保留上线日期在时间范围内的产品，适合「新产品」查询 |
| `--market us` | 市场/国家，例如 `us`、`jp`、`cn` |
| `--sources web,hacker_news` | 指定数据源 |
| `--limit 20` | 最多返回多少条 |
| `--include-raw` | 调试时包含原始数据 |

## 时间字段说明

输出中有三个和时间有关的概念：

```text
time_range           本次搜索窗口
published_at         证据页面、帖子、视频或讨论的发布时间
product_launch_date  产品自身的上线/首次发布日期
```

对于「最近新产品」这类查询，建议使用：

```bash
--filter-launch-date
```

这样 App Store 里那些很老但评分量巨大的产品不会混入结果。

## 配置 API Key

敏感信息不要写进代码仓库。推荐使用环境变量，或者写入：

```text
~/.config/what-just-launched/.env
```

脚本会优先读取环境变量，然后读取该 `.env` 文件。如果旧配置存在，也会兼容读取：

```text
~/.config/product-scout/.env
```

追加配置示例：

```bash
python scripts/just-launched.py --write-config TAVILY_API_KEY=your_key_here
python scripts/just-launched.py --write-config PRODUCT_SCOUT_WEB_PROVIDERS=tavily,duckduckgo,brave,exa
```

推荐配置：

```bash
# Product Hunt
PRODUCT_HUNT_TOKEN=

# Reddit OAuth，服务器上不要直接抓 Reddit HTML
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=linux:what-just-launched:0.1.0 (by /u/your_username)

# X / Twitter
XQUIK_API_KEY=
XAI_API_KEY=
PRODUCT_SCOUT_X_ADAPTER_COMMAND=

# YouTube
YOUTUBE_API_KEY=

# Web Search
PRODUCT_SCOUT_WEB_PROVIDERS=tavily,duckduckgo,brave,exa
TAVILY_API_KEY=
BRAVE_API_KEY=
EXA_API_KEY=
SERPER_API_KEY=
```

## Web Search Provider

默认支持：

```text
brave,exa,serper,tavily,duckduckgo
```

推荐实际使用：

```text
tavily,duckduckgo,brave,exa
```

DuckDuckGo 不需要 key，但只适合作为低频 fallback，不建议批量高并发使用。

## 安全说明

- 不要提交 `.env`、API key、browser cookie、GitHub token。
- Reddit 默认走 OAuth，不建议服务器直接抓 HTML，避免 403 或 IP 风控。
- X/Twitter 的 cookie 方式只适合本地、用户授权场景，不要把 cookie 写入仓库。
- 如果 token 曾经出现在聊天或日志里，建议立即在对应平台吊销并重新生成。

## 输出格式

脚本输出 JSON，核心结构如下：

```json
{
  "query": "new AI products",
  "mode": "discovery",
  "market": "us",
  "days": 7,
  "time_range": {
    "since": "2026-06-30",
    "until": "2026-07-06"
  },
  "ranking_model": {
    "name": "source-normalized-weighted-rrf",
    "rrf_k": 60
  },
  "results": [
    {
      "source": "hacker_news",
      "kind": "post",
      "title": "Launch HN: Example",
      "url": "https://example.com",
      "summary": "Short evidence text",
      "published_at": "2026-07-02T15:11:20Z",
      "product_launch_date": "",
      "signals": {
        "points": 109,
        "comments": 70
      },
      "ranking": {
        "final_score": 0.812345,
        "matched_sources": ["hacker_news"],
        "launch_date_confidence": "evidence_date_only"
      }
    }
  ]
}
```

排序时优先使用 `ranking.final_score`。`score` 是各来源自己的原始分数，不同平台之间不能直接比较。

## 目前限制

- Product Hunt 需要 token 才能直接拉发布数据。
- GitHub 未认证请求可能遇到 rate limit。
- App Store / iTunes 搜索适合补充 App 元数据，但不是所有结果都代表「最近上线」。
- Web Search 结果可能是目录页或资讯页，需要 Codex 二次筛选具体产品。
- 某些来源只能证明「讨论时间」，不能证明产品真实上线日期。

## 适合的查询词

```text
new AI products
new AI products launched this week
new mobile apps
new AI agents
new AI coding tools
new AI video tools
Show HN AI tool
Launch HN startup
Product Hunt AI agents
```
