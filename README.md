# What Just Launched Skill

Codex skill for discovering recently launched products, apps, AI tools, startup launches, and early market signals.

Choose a language:

- [中文文档](README.zh-CN.md)
- [English documentation](README.en.md)

## Skill Location

```text
skills/what-just-launched
```

## Quick Example

```bash
cd skills/what-just-launched
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

For a strict launch-date window:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

Do not commit API keys, browser cookies, or `.env` files.
