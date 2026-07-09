# What Just Launched

`what-just-launched` 是一个用于发现最近上线产品的工具。它聚焦回答一个问题：

```text
最近刚上线了什么值得关注的新产品？
```

它会从产品发布平台、应用商店、开发者社区、社区资讯搜索和用户反馈源中收集信号，输出结构化 JSON，再交给 Agent 生成产品简报。

## 安装

推荐使用开放 Agent Skills CLI。它支持 Codex、Claude Code、Cursor、OpenCode、Gemini CLI、Copilot 等兼容工具。

```bash
npx skills add Garcke/what-just-launched-skill -g
```

`-g` 表示安装到用户全局目录，所有项目都能使用。不加 `-g` 则安装到当前项目。

### 指定 Agent 安装

只安装到 Codex：

```bash
npx skills add Garcke/what-just-launched-skill -g -a codex
```

只安装到 Claude Code：

```bash
npx skills add Garcke/what-just-launched-skill -g -a claude-code
```

只安装到 Cursor：

```bash
npx skills add Garcke/what-just-launched-skill -g -a cursor
```

只安装到 OpenCode：

```bash
npx skills add Garcke/what-just-launched-skill -g -a opencode
```

同时安装到多个 Agent：

```bash
npx skills add Garcke/what-just-launched-skill -g -a codex -a cursor -a claude-code
```

安装前查看仓库里有哪些可安装项：

```bash
npx skills add Garcke/what-just-launched-skill --list
```

后续更新：

```bash
npx skills update what-just-launched -g
```

查看或卸载：

```bash
npx skills list -g
npx skills remove what-just-launched -g
```

### Claude Code 指令安装

如果想让 Claude Code 自己执行安装，可以把这段话发给 Claude Code：

```text
Install the Agent Skill from https://github.com/Garcke/what-just-launched-skill for Claude Code using:
npx skills add Garcke/what-just-launched-skill -g -a claude-code
Then run the skill's preflight or diagnose command and summarize which sources are configured.
```

如果以后这个项目进入 Claude Code marketplace，再优先使用 marketplace 安装，因为 marketplace 更适合插件式自动更新。现在先使用 `npx skills`。

### 手动开发安装

需要本地修改源码时使用：

```bash
git clone https://github.com/Garcke/what-just-launched-skill.git
cd what-just-launched-skill
```

安装到 Codex：

```bash
mkdir -p ~/.codex/skills
cp -R skills/what-just-launched ~/.codex/skills/
```

安装到 Claude Code：

```bash
mkdir -p ~/.claude/skills
cp -R skills/what-just-launched ~/.claude/skills/
```

Windows PowerShell 示例：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills"
Copy-Item -Recurse -Force "skills\what-just-launched" "$env:USERPROFILE\.codex\skills\"
```

## 配置

不要把密钥提交到仓库。API key 可以放在环境变量里，也可以放在：

```text
~/.config/what-just-launched/.env
```

脚本会先读环境变量，再读这个 `.env` 文件。也兼容旧路径：

```text
~/.config/product-scout/.env
```

安全追加配置：

```bash
python scripts/just-launched.py --write-config KEY=VALUE
```

### 最小可用配置

部分来源不需要 key，例如 Hacker News、GitHub Trending、Apple 公共接口、Uneed、Fazier、Stack Exchange、Lobsters。

检查当前可用来源：

```bash
python scripts/just-launched.py --preflight
python scripts/just-launched.py --diagnose
```

### 推荐配置

```bash
# 产品发现
python scripts/just-launched.py --write-config PRODUCT_HUNT_TOKEN=<product_hunt_token>

# Web Search
python scripts/just-launched.py --write-config SERPAPI_API_KEY=<serpapi_key>
python scripts/just-launched.py --write-config TAVILY_API_KEY=<tavily_key>

# 页面解析辅助，用于 BetaList、Microlaunch、Fazier 等页面型来源
python scripts/just-launched.py --write-config FIRECRAWL_API_KEY=<firecrawl_key>
```

### 完整 `.env` 模板

```bash
# Product Hunt
PRODUCT_HUNT_TOKEN=
PRODUCT_SCOUT_PRODUCT_HUNT_TOPIC=

# Reddit OAuth
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=linux:what-just-launched:0.1.0 (by /u/your_username)
PRODUCT_SCOUT_REDDIT_COMMENTS=true

# X / Twitter
XQUIK_API_KEY=
XAI_API_KEY=
PRODUCT_SCOUT_X_ADAPTER_COMMAND=

# YouTube
YOUTUBE_API_KEY=
PRODUCT_SCOUT_YOUTUBE_COMMENTS=false

# Web Search
PRODUCT_SCOUT_WEB_PROVIDERS=brave,serpapi,tavily
BRAVE_API_KEY=
SERPAPI_API_KEY=
TAVILY_API_KEY=

# 页面解析辅助
FIRECRAWL_API_KEY=
```

## 使用

查询最近 7 天的新 AI 产品：

```bash
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

使用明确时间范围，并按产品上线日期过滤：

```bash
python scripts/just-launched.py "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

查询某个产品的用户反馈：

```bash
python scripts/just-launched.py "Cursor AI reviews" --mode feedback --days 30 --sources hacker_news,github_issues
```

分别指定产品源和反馈源：

```bash
python scripts/just-launched.py "AI coding tools" --mode all --product-sources product_hunt,github_trending,uneed,fazier --feedback-sources web,hacker_news,reddit --days 7
```

## 数据源

### 产品发现源

| 来源 | 用途 | 访问方式 |
|---|---|---|
| Product Hunt | SaaS、AI 工具、独立产品、发布榜 | `PRODUCT_HUNT_TOKEN` |
| Hacker News | Show HN、Launch HN、开发者产品 | HN Algolia API |
| GitHub Trending | 开源项目和开发者工具 | 公开页面，可选 Firecrawl 解析 |
| Apple RSS / iTunes Search | iOS 榜单和应用元数据 | Apple 公共 API |
| Google Play / AppBrain | Android 应用发现补充 | AppBrain 页面搜索 |
| BetaList | 早期 startup / waitlist 产品 | 公开页面，可选 Firecrawl 解析 |
| Microlaunch | 独立产品、SaaS、AI 工具 | 公开页面，可选 Firecrawl 解析 |
| Uneed | 独立产品和发布页 | 公开 daily ladder API，可选 Firecrawl fallback |
| Fazier | 每日产品发布和独立产品 | 公开页面，可选 Firecrawl 解析 |

### 反馈和市场信号源

| 来源 | 用途 | 访问方式 |
|---|---|---|
| Reddit | 用户讨论、抱怨、对比 | OAuth 优先 |
| Reddit Public JSON | 本地低频 fallback | 显式启用 |
| GitHub Issues | Bug、功能需求、开发者反馈 | GitHub 公开 Search API |
| Stack Exchange | 技术问题和集成痛点 | Stack Exchange 公共 API |
| Lobsters | 开发者社区讨论 | 公开页面 |
| X / Twitter | 发布反应和社交信号 | `XQUIK_API_KEY` 或 adapter |
| YouTube | 测评、教程、评论 | `YOUTUBE_API_KEY` |
| Hacker News | 开发者反馈和质疑 | HN Algolia API |
| Web Search | 评测、对比、发布榜、资讯证据 | Brave / SerpApi / Tavily |

## 输出结构

脚本输出标准 JSON：

```json
{
  "query": "new AI products",
  "mode": "discovery",
  "time_range": {
    "since": "2026-07-01",
    "until": "2026-07-07"
  },
  "products": [],
  "product_data": [],
  "community_feedback": [],
  "results": [],
  "preflight": [],
  "errors": []
}
```

`products` 是产品发现主视图。`product_data` 是来源级产品证据。`community_feedback` 是讨论、社交、视频和 Web Search 反馈证据。`results` 保留为兼容旧用法的混合排序列表。

## 安全说明

- 不要提交 `.env`、API key、浏览器 cookie 或 GitHub token。
- Reddit 建议使用 OAuth，不建议服务器直接抓 Reddit HTML。
- X/Twitter cookie 方式只适合本地、用户授权的场景。
- 如果 token 出现在聊天或日志里，建议立刻吊销并重新生成。

## 发布规则

每次推送到 GitHub 后，都需要创建新的版本 tag 和 GitHub Release。版本号使用 `vMAJOR.MINOR.PATCH`，例如 `v1.8.2`。
