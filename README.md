# What Just Launched Skill

Codex skill for discovering recently launched products, apps, AI tools, startup launches, and early market signals.

## Skill

The skill lives at:

```text
skills/what-just-launched
```

It searches across launch platforms, app stores, developer communities, social/video feedback sources, and web search.

## Quick Start

From the skill directory:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

For explicit launch windows:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

## Configuration

Secrets should be provided via environment variables or:

```text
~/.config/what-just-launched/.env
```

Do not commit API keys, cookies, or `.env` files.

