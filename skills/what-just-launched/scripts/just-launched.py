#!/usr/bin/env python3
"""Compatibility wrapper for the What Just Launched CLI."""

from __future__ import annotations

from just_launched.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
