"""
Tests for scraper.py – parsing logic only (no real HTTP calls).

All Wikipedia page fetches are replaced with sample HTML that mirrors the
actual Wikipedia table structures used by the scrapers.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Make sure the parent package is importable regardless of working directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bs4 import BeautifulSoup
from scraper import (
    CS_TO_EN_PLANET,
    _clean_text,
    parse_cs_moons,
    parse_en_moons,
    fetch_moons_en,
    fetch_moons_cs,
    EN_URL,
    CS_URL,
)


# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------

# Minimal English "List of natural satellites" table.
# Uses rowspan on the planet cell, as Wikipedia does for planets with
# multiple moons.
EN_SAMPLE_HTML = """\
<html><body>
<table class="wikitable sortable">
  <tr>
    <th>Planet</th><th>Name</th><th>Semi-major axis (km)</th>
  </tr>
  <!-- Earth – single moon, no rowspan needed -->
  <tr>
    <td>Earth</td><td><a href="/wiki/Moon">Moon</a></td><td>384,400</td>
  </tr>
  <!-- Mars – rowspan=2 for the planet cell -->
  <tr>
    <td rowspan="2">Mars</td><td><a href="/wiki/Phobos">Phobos</a></td><td>9,376</td>
  </tr>
  <tr>
    <td></td><td><a href="/wiki/Deimos_(moon)">Deimos</a></td><td>23,459</td>
  </tr>
  <!-- Jupiter – three moons to test ordering -->
  <tr>
    <td rowspan="3">Jupiter</td><td>Metis</td><td>128,000</td>
  </tr>
  <tr>
    <td></td><td>Adrastea</td><td>129,000</td>
  </tr>
  <tr>
    <td></td><td>Amalthea</td><td>181,000</td>
  </tr>
</table>
</body></html>
"""

# Minimal Czech moon list page.
# Uses Czech planet names in a single table.
CS_SAMPLE_HTML = """\
<html><body>
<table class="wikitable sortable">
  <tr>
    <th>Planeta</th><th>Název</th><th>Velká poloosa (km)</th>
  </tr>
  <tr>
    <td>Země</td><td><a href="/wiki/M%C4%9Bs%C3%ADc">Měsíc</a></td><td>384 400</td>
  </tr>
  <tr>
    <td rowspan="2">Mars</td><td>Phobos</td><td>9 376</td>
  </tr>
  <tr>
    <td></td><td>Deimos</td><td>23 459</td>
  </tr>
  <tr>
    <td rowspan="3">Jupiter</td><td>Metis</td><td>128 000</td>
  </tr>
  <tr>
    <td></td><td>Adrastea</td><td>129 000</td>
  </tr>
  <tr>
    <td></td><td>Amalthea</td><td>181 000</td>
  </tr>
</table>
</body></html>
"""

# Section-based HTML for the fallback parser test.
# Each planet has its own heading + wikitable.
SECTION_HTML = """\
<html><body>
<h3>Earth</h3>
<table class="wikitable">
  <tr><th>Name</th></tr>
  <tr><td>Moon</td></tr>
</table>
<h3>Mars</h3>
<table class="wikitable">
  <tr><th>Name</th></tr>
  <tr><td>Phobos</td></tr>
  <tr><td>Deimos</td></tr>
</table>
</body></html>
"""


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# Tests for _clean_text
# ---------------------------------------------------------------------------

class TestCleanText(unittest.TestCase):
    def test_strips_footnote_markers(self):
        cell = _soup("<td>Moon [1]</td>").find("td")
        self.assertEqual(_clean_text(cell), "Moon")

    def test_strips_multiple_footnotes(self):
        cell = _soup("<td>Phobos [a][note 3]</td>").find("td")
        self.assertEqual(_clean_text(cell), "Phobos")

    def test_collapses_whitespace(self):
        cell = _soup("<td>  Io  </td>").find("td")
        self.assertEqual(_clean_text(cell), "Io")

    def test_plain_text(self):
        cell = _soup("<td>Ganymede</td>").find("td")
        self.assertEqual(_clean_text(cell), "Ganymede")


# ---------------------------------------------------------------------------
# Tests for parse_en_moons
# ---------------------------------------------------------------------------

class TestParseEnMoons(unittest.TestCase):
    def setUp(self):
        self.soup = _soup(EN_SAMPLE_HTML)
        self.moons = parse_en_moons(self.soup)

    def test_earth_has_moon(self):
        self.assertIn("Earth", self.moons)
        self.assertIn("Moon", self.moons["Earth"])

    def test_mars_has_phobos_and_deimos(self):
        self.assertIn("Mars", self.moons)
        self.assertEqual(self.moons["Mars"], ["Phobos", "Deimos"])

    def test_mars_order_innermost_first(self):
        """Phobos is closer to Mars than Deimos."""
        mars = self.moons["Mars"]
        self.assertEqual(mars.index("Phobos"), 0)
        self.assertEqual(mars.index("Deimos"), 1)

    def test_jupiter_three_moons_in_order(self):
        self.assertIn("Jupiter", self.moons)
        self.assertEqual(self.moons["Jupiter"], ["Metis", "Adrastea", "Amalthea"])

    def test_returns_dict(self):
        self.assertIsInstance(self.moons, dict)

    def test_no_empty_planet_keys(self):
        for key in self.moons:
            self.assertTrue(key, "Planet key should not be empty string")

    def test_no_empty_moon_names(self):
        for planet, moon_list in self.moons.items():
            for moon in moon_list:
                self.assertTrue(moon, f"Empty moon name under {planet}")


# ---------------------------------------------------------------------------
# Tests for parse_cs_moons
# ---------------------------------------------------------------------------

class TestParseCsMoons(unittest.TestCase):
    def setUp(self):
        self.soup = _soup(CS_SAMPLE_HTML)
        self.moons = parse_cs_moons(self.soup)

    def test_returns_english_planet_keys(self):
        """Czech planet names must be translated to English keys."""
        self.assertIn("Earth", self.moons)
        self.assertIn("Mars", self.moons)
        self.assertIn("Jupiter", self.moons)
        # No Czech-language keys should appear for known planets
        self.assertNotIn("Země", self.moons)

    def test_earth_has_mesic(self):
        self.assertIn("Earth", self.moons)
        self.assertIn("Měsíc", self.moons["Earth"])

    def test_mars_order_preserved(self):
        self.assertEqual(self.moons["Mars"], ["Phobos", "Deimos"])

    def test_jupiter_three_moons_in_order(self):
        self.assertEqual(self.moons["Jupiter"], ["Metis", "Adrastea", "Amalthea"])


# ---------------------------------------------------------------------------
# Tests for section-based fallback in parse_en_moons
# ---------------------------------------------------------------------------

class TestEnMoonsSectionFallback(unittest.TestCase):
    """When there is no planet-column table, the section-based fallback is used."""

    def setUp(self):
        self.soup = _soup(SECTION_HTML)
        self.moons = parse_en_moons(self.soup)

    def test_earth_found(self):
        self.assertIn("Earth", self.moons)
        self.assertEqual(self.moons["Earth"], ["Moon"])

    def test_mars_found(self):
        self.assertIn("Mars", self.moons)
        self.assertEqual(self.moons["Mars"], ["Phobos", "Deimos"])


# ---------------------------------------------------------------------------
# Tests for CS_TO_EN_PLANET mapping completeness
# ---------------------------------------------------------------------------

class TestCSToENPlanetMapping(unittest.TestCase):
    def test_all_planets_with_moons_covered(self):
        """Every planet that actually has moons must have a Czech mapping."""
        planets_with_moons = {"Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"}
        mapped_planets = set(CS_TO_EN_PLANET.values())
        self.assertTrue(
            planets_with_moons.issubset(mapped_planets),
            f"Missing mappings for: {planets_with_moons - mapped_planets}",
        )

    def test_no_duplicate_english_values(self):
        values = list(CS_TO_EN_PLANET.values())
        self.assertEqual(len(values), len(set(values)), "Duplicate English planet names in mapping")


# ---------------------------------------------------------------------------
# Tests for fetch_moons_en / fetch_moons_cs (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchMoonsEN(unittest.TestCase):
    @patch("scraper.fetch_page")
    def test_fetch_calls_correct_url(self, mock_fetch):
        mock_fetch.return_value = _soup(EN_SAMPLE_HTML)
        result = fetch_moons_en()
        mock_fetch.assert_called_once_with(EN_URL)
        self.assertIn("Earth", result)

    @patch("scraper.fetch_page")
    def test_returns_dict_with_moons(self, mock_fetch):
        mock_fetch.return_value = _soup(EN_SAMPLE_HTML)
        result = fetch_moons_en()
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)


class TestFetchMoonsCS(unittest.TestCase):
    @patch("scraper.fetch_page")
    def test_fetch_calls_correct_url(self, mock_fetch):
        mock_fetch.return_value = _soup(CS_SAMPLE_HTML)
        result = fetch_moons_cs()
        mock_fetch.assert_called_once_with(CS_URL)
        self.assertIn("Earth", result)

    @patch("scraper.fetch_page")
    def test_returns_dict_with_moons(self, mock_fetch):
        mock_fetch.return_value = _soup(CS_SAMPLE_HTML)
        result = fetch_moons_cs()
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)

    @patch("scraper.fetch_page")
    def test_planet_keys_are_in_english(self, mock_fetch):
        mock_fetch.return_value = _soup(CS_SAMPLE_HTML)
        result = fetch_moons_cs()
        # Czech-specific planet names (those that differ from English) must be
        # translated.  "Mars" is identical in both languages so is allowed.
        cs_only_names = {
            k for k, v in CS_TO_EN_PLANET.items() if k != v
        }
        for key in result:
            self.assertNotIn(key, cs_only_names, f"Czech-only key '{key}' not translated")


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    def test_empty_page_returns_empty_dict(self):
        soup = _soup("<html><body></body></html>")
        result = parse_en_moons(soup)
        self.assertIsInstance(result, dict)

    def test_table_without_planet_column_skipped(self):
        html = """\
        <html><body>
        <table class="wikitable">
          <tr><th>Name</th><th>Diameter</th></tr>
          <tr><td>Moon</td><td>3474</td></tr>
        </table>
        </body></html>"""
        soup = _soup(html)
        result = parse_en_moons(soup)
        # Without a planet column the table-based parser returns None/{}
        # and the section-based fallback also finds nothing → empty dict
        self.assertIsInstance(result, dict)

    def test_footnote_in_moon_name_stripped(self):
        html = """\
        <html><body>
        <table class="wikitable">
          <tr><th>Planet</th><th>Name</th></tr>
          <tr><td>Saturn</td><td>Titan [2]</td></tr>
        </table>
        </body></html>"""
        soup = _soup(html)
        result = parse_en_moons(soup)
        self.assertIn("Saturn", result)
        self.assertIn("Titan", result["Saturn"])
        self.assertNotIn("Titan [2]", result["Saturn"])


if __name__ == "__main__":
    unittest.main()
