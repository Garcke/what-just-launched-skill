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
      }
    }
  ]
}
```

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

