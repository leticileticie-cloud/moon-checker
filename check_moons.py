#!/usr/bin/env python3
"""
check_moons.py – Check Wikipedia moon lists for changes.

Loads the locally stored moon database (produced by ``init_moons.py``) and
compares it against the live English and Czech Wikipedia pages.  Alerts are
printed when:

* A moon has been **added** to Wikipedia since the last snapshot.
* A moon has been **removed** from Wikipedia since the last snapshot.
* The **order** of moons for a planet has changed (indicating a distance
  re-measurement or re-classification).
* The English and Czech lists **differ** from each other.

Usage::

    python check_moons.py [--db moons.json]

Exit codes:
    0  No changes detected.
    1  One or more changes or discrepancies detected.
    2  The database file does not exist (run init_moons.py first).
"""

import argparse
import json
import sys
from typing import NamedTuple

from scraper import DB_FILE, fetch_moons_cs, fetch_moons_en


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

class PlanetDiff(NamedTuple):
    planet: str
    added: list[str]
    removed: list[str]
    reordered: bool


def diff_planet(
    stored: list[str], live: list[str], planet: str
) -> PlanetDiff | None:
    """Return a :class:`PlanetDiff` if any change is detected, else ``None``."""
    stored_set = set(stored)
    live_set = set(live)
    added = [m for m in live if m not in stored_set]
    removed = [m for m in stored if m not in live_set]

    # Check order of moons present in both snapshots
    common_stored = [m for m in stored if m in live_set]
    common_live = [m for m in live if m in stored_set]
    reordered = common_stored != common_live

    if added or removed or reordered:
        return PlanetDiff(planet, added, removed, reordered)
    return None


def diff_language(
    stored: dict[str, list[str]],
    live: dict[str, list[str]],
    lang_label: str,
) -> list[PlanetDiff]:
    """Return all planet diffs between *stored* and *live* for one language."""
    all_planets = set(stored) | set(live)
    diffs = []
    for planet in sorted(all_planets):
        d = diff_planet(stored.get(planet, []), live.get(planet, []), planet)
        if d:
            diffs.append(d)
    return diffs


def diff_between_languages(
    en_live: dict[str, list[str]],
    cs_live: dict[str, list[str]],
) -> dict[str, dict]:
    """
    Compare live EN and CS data.

    Returns a dict of planet → {only_en, only_cs, reordered} for every
    planet where the two editions differ.
    """
    all_planets = set(en_live) | set(cs_live)
    result = {}
    for planet in sorted(all_planets):
        en_moons = set(en_live.get(planet, []))
        cs_moons = set(cs_live.get(planet, []))
        only_en = sorted(en_moons - cs_moons)
        only_cs = sorted(cs_moons - en_moons)
        if only_en or only_cs:
            result[planet] = {"only_in_en": only_en, "only_in_cs": only_cs}
    return result


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

SEPARATOR = "─" * 60


def _print_lang_diffs(diffs: list[PlanetDiff], lang_label: str) -> None:
    if not diffs:
        print(f"  [{lang_label}] No changes detected.")
        return
    for d in diffs:
        print(f"  [{lang_label}] {d.planet}:")
        if d.added:
            print(f"      + Added  : {', '.join(d.added)}")
        if d.removed:
            print(f"      - Removed: {', '.join(d.removed)}")
        if d.reordered:
            print("      ~ Order changed (distance re-classification?)")


def _print_lang_discrepancies(discrepancies: dict[str, dict]) -> None:
    if not discrepancies:
        print("  No discrepancies between EN and CS lists.")
        return
    print("  ⚠  The English and Czech lists differ:")
    for planet, diff in discrepancies.items():
        print(f"     {planet}:")
        if diff["only_in_en"]:
            print(f"       Only in EN : {', '.join(diff['only_in_en'])}")
        if diff["only_in_cs"]:
            print(f"       Only in CS : {', '.join(diff['only_in_cs'])}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_database(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(
            f"ERROR: Database file '{path}' not found.\n"
            "Run 'python init_moons.py' first to initialise the database.",
            file=sys.stderr,
        )
        sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=DB_FILE,
        help=f"Path to the JSON database file (default: {DB_FILE})",
    )
    args = parser.parse_args()

    db = load_database(args.db)
    stored_en: dict[str, list[str]] = db.get("en", {})
    stored_cs: dict[str, list[str]] = db.get("cs", {})
    last_updated = db.get("last_updated", "unknown")

    print(f"Database last updated: {last_updated}")
    print("Fetching current data from Wikipedia …\n")

    print("Fetching English Wikipedia …")
    live_en = fetch_moons_en()

    print("Fetching Czech Wikipedia …")
    live_cs = fetch_moons_cs()

    print(f"\n{SEPARATOR}")
    print(" CHANGES vs STORED SNAPSHOT")
    print(SEPARATOR)

    en_diffs = diff_language(stored_en, live_en, "EN")
    cs_diffs = diff_language(stored_cs, live_cs, "CS")

    _print_lang_diffs(en_diffs, "EN")
    _print_lang_diffs(cs_diffs, "CS")

    print(f"\n{SEPARATOR}")
    print(" EN vs CS DISCREPANCIES (live data)")
    print(SEPARATOR)

    discrepancies = diff_between_languages(live_en, live_cs)
    _print_lang_discrepancies(discrepancies)

    print(SEPARATOR)

    any_issue = bool(en_diffs or cs_diffs or discrepancies)
    if any_issue:
        print("\n⚠  Action recommended: review the alerts above.")
        print("   Re-run 'python init_moons.py' after verifying the changes.")
        sys.exit(1)
    else:
        print("\n✓  All clear. No changes or discrepancies found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
