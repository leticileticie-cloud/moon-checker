"""Shared scraping/parsing logic for fetching moon lists from Wikipedia."""

import re
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_FILE = "moons.json"

# Wikipedia pages that list natural satellites sorted by distance from planet.
# English page: "List of natural satellites"
EN_URL = "https://en.wikipedia.org/wiki/List_of_natural_satellites"
# Czech page: "Přirozený měsíc" (equivalent listing in Czech Wikipedia)
CS_URL = "https://cs.wikipedia.org/wiki/P%C5%99irozen%C3%BD_m%C4%9Bs%C3%ADc"

# Planet names in order (Mercury & Venus have no moons; included for completeness)
PLANET_ORDER = [
    "Mercury", "Venus", "Earth", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune",
]

# Czech planet name → canonical English planet name
CS_TO_EN_PLANET = {
    "Merkur": "Mercury",
    "Venuše": "Venus",
    "Země": "Earth",
    "Mars": "Mars",
    "Jupiter": "Jupiter",
    "Saturn": "Saturn",
    "Uran": "Uranus",
    "Neptun": "Neptune",
}

HEADERS = {
    "User-Agent": (
        "moon-checker/1.0 "
        "(https://github.com/leticileticie-cloud/moon-checker; "
        "checking solar system moon lists)"
    )
}

REQUEST_TIMEOUT = 30


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> BeautifulSoup:
    """Fetch *url* and return a :class:`BeautifulSoup` parse tree.

    Raises:
        requests.exceptions.HTTPError: if the HTTP response status is 4xx/5xx.
        requests.exceptions.ConnectionError: on network connectivity problems.
        requests.exceptions.Timeout: if the request exceeds ``REQUEST_TIMEOUT``.
        requests.exceptions.RequestException: for any other request failure.
    """
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _clean_text(element) -> str:
    """Return plain text from a BeautifulSoup tag, removing footnote markers."""
    text = element.get_text(" ", strip=True)
    # Remove Wikipedia footnote markers like [1], [a], [note 1] …
    text = re.sub(r"\[[\w\s]+\]", "", text)
    # Collapse extra whitespace
    text = " ".join(text.split())
    return text


def _column_index(headers: list[str], candidates: list[str]) -> int | None:
    """Return the first header index whose lower-case text matches any candidate."""
    for i, h in enumerate(headers):
        if h.lower() in candidates:
            return i
    return None


def _parse_wikitable_by_planet_column(
    table, planet_candidates: list[str], name_candidates: list[str]
) -> dict[str, list[str]] | None:
    """
    Parse a wikitable that has distinct 'planet' and 'name' columns.

    The planet cell may use ``rowspan`` to span multiple moon rows (a common
    Wikipedia pattern), so we track the current planet across rows.

    Returns a ``{planet: [moon, …]}`` dict, preserving row order, or
    ``None`` if the expected columns are not found.
    """
    rows = table.find_all("tr")
    if len(rows) < 2:
        return None

    # Build header list from the first row
    header_cells = rows[0].find_all(["th", "td"])
    headers = [_clean_text(c).lower() for c in header_cells]

    planet_col = _column_index(headers, planet_candidates)
    name_col = _column_index(headers, name_candidates)
    if planet_col is None or name_col is None:
        return None

    moons: dict[str, list[str]] = {}
    current_planet: str | None = None

    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        # Try to find an explicit planet cell in this row.
        # When rowspan is used the planet column cell may be absent; in that
        # case we fall through and keep current_planet.
        if len(cells) > planet_col:
            candidate = _clean_text(cells[planet_col])
            if candidate:
                current_planet = candidate

        if current_planet is None or len(cells) <= name_col:
            continue

        moon_name = _clean_text(cells[name_col])
        # Skip rows that look like column sub-headers.
        # We use a case-insensitive comparison but exclude "moon" from the
        # skip-list because "Moon" is the legitimate name of Earth's satellite.
        if not moon_name or moon_name.lower() in {"name", "satellite"}:
            continue

        moons.setdefault(current_planet, []).append(moon_name)

    return moons if moons else None


def _parse_wikitable_by_sections(soup, planet_names: list[str]) -> dict[str, list[str]]:
    """
    Fallback parser: look for headings that match planet names and collect
    moon names from the first wikitable beneath each heading.

    Returns a ``{planet: [moon, …]}`` dict.
    """
    moons: dict[str, list[str]] = {}
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = _clean_text(heading)
        matched_planet: str | None = None
        for planet in planet_names:
            if planet.lower() in heading_text.lower():
                matched_planet = planet
                break
        if matched_planet is None:
            continue

        # Walk siblings until we find a wikitable
        for sibling in heading.find_next_siblings():
            if sibling.name in {"h2", "h3", "h4"}:
                break  # next section; stop
            if sibling.name == "table" and "wikitable" in sibling.get("class", []):
                for row in sibling.find_all("tr")[1:]:
                    cells = row.find_all(["td", "th"])
                    if cells:
                        name = _clean_text(cells[0])
                        if name:
                            moons.setdefault(matched_planet, []).append(name)
                break

    return moons


# ---------------------------------------------------------------------------
# Language-specific fetchers
# ---------------------------------------------------------------------------

def parse_en_moons(soup: BeautifulSoup) -> dict[str, list[str]]:
    """
    Parse the English "List of natural satellites" Wikipedia page.

    Returns ``{planet_name: [moon_name, …]}`` with moons ordered by
    distance from planet (innermost first).
    """
    planet_candidates = ["planet", "body", "parent body"]
    name_candidates = ["name", "satellite", "moon"]

    for table in soup.find_all("table", class_="wikitable"):
        result = _parse_wikitable_by_planet_column(table, planet_candidates, name_candidates)
        if result:
            return result

    # Fallback: section-based parsing
    return _parse_wikitable_by_sections(soup, PLANET_ORDER)


def parse_cs_moons(soup: BeautifulSoup) -> dict[str, list[str]]:
    """
    Parse the Czech Wikipedia moon-list page.

    Czech planet names are normalised to English equivalents so the two
    datasets use the same keys.

    Returns ``{planet_name_en: [moon_name_cs, …]}``.
    """
    planet_candidates = ["planeta", "těleso", "mateřské těleso"]
    name_candidates = ["název", "jméno", "měsíc", "satelit", "name"]

    for table in soup.find_all("table", class_="wikitable"):
        result = _parse_wikitable_by_planet_column(table, planet_candidates, name_candidates)
        if result:
            # Normalise planet names to English
            normalised: dict[str, list[str]] = {}
            for planet_cs, moon_list in result.items():
                planet_en = CS_TO_EN_PLANET.get(planet_cs, planet_cs)
                normalised[planet_en] = moon_list
            return normalised

    # Fallback: section-based parsing using Czech planet names
    cs_planet_names = list(CS_TO_EN_PLANET.keys())
    raw = _parse_wikitable_by_sections(soup, cs_planet_names)
    return {CS_TO_EN_PLANET.get(p, p): moons for p, moons in raw.items()}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def fetch_moons_en() -> dict[str, list[str]]:
    """Fetch and parse the English Wikipedia moon list."""
    soup = fetch_page(EN_URL)
    return parse_en_moons(soup)


def fetch_moons_cs() -> dict[str, list[str]]:
    """Fetch and parse the Czech Wikipedia moon list (planet keys in English)."""
    soup = fetch_page(CS_URL)
    return parse_cs_moons(soup)
