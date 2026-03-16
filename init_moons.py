#!/usr/bin/env python3
"""
init_moons.py – Initialise the local moon database.

Fetches the list of natural satellites for each solar-system planet from both
English and Czech Wikipedia, then writes the data to ``moons.json``.  Moons
are stored in distance order (innermost first) as supplied by Wikipedia.

Usage::

    python init_moons.py [--output moons.json]
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from scraper import DB_FILE, fetch_moons_cs, fetch_moons_en


def build_database() -> dict:
    """Fetch moon data from both Wikipedia editions and return the combined dict."""
    print("Fetching moon list from English Wikipedia …")
    en_moons = fetch_moons_en()
    if not en_moons:
        print("ERROR: Failed to parse English Wikipedia moon list.", file=sys.stderr)
        sys.exit(1)

    print("Fetching moon list from Czech Wikipedia …")
    cs_moons = fetch_moons_cs()
    if not cs_moons:
        print("ERROR: Failed to parse Czech Wikipedia moon list.", file=sys.stderr)
        sys.exit(1)

    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "en": en_moons,
        "cs": cs_moons,
    }


def save_database(data: dict, path: str) -> None:
    """Write *data* as pretty-printed JSON to *path*."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"Database saved to '{path}'.")


def print_summary(data: dict) -> None:
    """Print a brief summary of what was stored."""
    print("\n── Summary ──────────────────────────────────────")
    for lang in ("en", "cs"):
        moons_by_planet = data.get(lang, {})
        total = sum(len(v) for v in moons_by_planet.values())
        print(f"  [{lang.upper()}] {len(moons_by_planet)} planets, {total} moons total")
        planet_keys = list(moons_by_planet)
        for planet in sorted(moons_by_planet, key=lambda p: planet_keys.index(p)):
            print(f"       {planet}: {len(moons_by_planet[planet])} moons")
    print("─────────────────────────────────────────────────")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=DB_FILE,
        help=f"Path for the output JSON file (default: {DB_FILE})",
    )
    args = parser.parse_args()

    data = build_database()
    save_database(data, args.output)
    print_summary(data)


if __name__ == "__main__":
    main()
