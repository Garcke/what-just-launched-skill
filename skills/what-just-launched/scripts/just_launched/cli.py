"""Command-line interface for What Just Launched."""

from __future__ import annotations

import argparse
import json

from .common import CONFIG_FILE, append_config, load_env_file
from .engine import ProductScout

def main(argv: list[str] | None = None) -> int:
    load_env_file()
    parser = argparse.ArgumentParser(prog="just-launched", description="Find recently launched products and early launch signals.")
    parser.add_argument("query", nargs="?", default="", help="Product, category, competitor, or market query.")
    parser.add_argument("--mode", choices=["discovery", "feedback", "all"], default="all")
    parser.add_argument("--sources", default="all", help="Comma-separated source ids or all.")
    parser.add_argument("--product-sources", default="all", help="Comma-separated product discovery source ids or all. Ignored when --sources is set.")
    parser.add_argument("--feedback-sources", default="all", help="Comma-separated community feedback source ids or all. Ignored when --sources is set.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--since", default="", help="Start date in YYYY-MM-DD. Overrides --days start.")
    parser.add_argument("--until", default="", help="End date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--market", default="us")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--filter-launch-date", action="store_true", help="Keep products only when product_launch_date is inside the time range. Best for new-product discovery.")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--write-config", action="append", default=[], metavar="KEY=VALUE", help="Append a missing key to ~/.config/what-just-launched/.env.")
    parser.add_argument("--include-raw", action="store_true", help="Include raw source payloads for debugging.")
    args = parser.parse_args(argv)

    if args.write_config:
        entries: dict[str, str] = {}
        for pair in args.write_config:
            if "=" not in pair:
                raise SystemExit(f"--write-config expects KEY=VALUE, got: {pair}")
            key, value = pair.split("=", 1)
            entries[key.strip()] = value.strip()
        append_config(entries)
        print(json.dumps({"config_file": str(CONFIG_FILE), "written_keys": sorted(entries.keys())}, ensure_ascii=False, indent=2))
        return 0

    scout = ProductScout(args)
    data = scout.diagnose() if args.diagnose else scout.preflight() if args.preflight else scout.run()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0

