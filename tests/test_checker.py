"""
Tests for check_moons.py – diff logic only (no real HTTP calls or disk I/O).
"""

import sys
import os
import json
import unittest
from io import StringIO
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from check_moons import (
    diff_planet,
    diff_language,
    diff_between_languages,
    load_database,
    PlanetDiff,
)


# ---------------------------------------------------------------------------
# Tests for diff_planet
# ---------------------------------------------------------------------------

class TestDiffPlanet(unittest.TestCase):
    def test_no_change(self):
        stored = ["Phobos", "Deimos"]
        live = ["Phobos", "Deimos"]
        self.assertIsNone(diff_planet(stored, live, "Mars"))

    def test_moon_added(self):
        stored = ["Phobos"]
        live = ["Phobos", "Deimos"]
        result = diff_planet(stored, live, "Mars")
        self.assertIsNotNone(result)
        self.assertEqual(result.added, ["Deimos"])
        self.assertEqual(result.removed, [])
        self.assertFalse(result.reordered)

    def test_moon_removed(self):
        stored = ["Phobos", "Deimos"]
        live = ["Phobos"]
        result = diff_planet(stored, live, "Mars")
        self.assertIsNotNone(result)
        self.assertEqual(result.added, [])
        self.assertEqual(result.removed, ["Deimos"])
        self.assertFalse(result.reordered)

    def test_moon_added_and_removed(self):
        stored = ["Phobos", "Deimos"]
        live = ["Phobos", "NewMoon"]
        result = diff_planet(stored, live, "Mars")
        self.assertIsNotNone(result)
        self.assertEqual(result.added, ["NewMoon"])
        self.assertEqual(result.removed, ["Deimos"])

    def test_reorder_detected(self):
        stored = ["Phobos", "Deimos"]
        live = ["Deimos", "Phobos"]
        result = diff_planet(stored, live, "Mars")
        self.assertIsNotNone(result)
        self.assertTrue(result.reordered)

    def test_empty_both_no_diff(self):
        self.assertIsNone(diff_planet([], [], "Mercury"))

    def test_planet_name_preserved(self):
        stored = ["Moon"]
        live = ["Moon", "NewMoon"]
        result = diff_planet(stored, live, "Earth")
        self.assertEqual(result.planet, "Earth")


# ---------------------------------------------------------------------------
# Tests for diff_language
# ---------------------------------------------------------------------------

class TestDiffLanguage(unittest.TestCase):
    def _stored(self):
        return {
            "Earth": ["Moon"],
            "Mars": ["Phobos", "Deimos"],
        }

    def test_no_changes_returns_empty(self):
        live = self._stored()
        result = diff_language(self._stored(), live, "EN")
        self.assertEqual(result, [])

    def test_new_planet_detected(self):
        stored = {"Earth": ["Moon"]}
        live = {"Earth": ["Moon"], "Mars": ["Phobos"]}
        result = diff_language(stored, live, "EN")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].planet, "Mars")
        self.assertEqual(result[0].added, ["Phobos"])

    def test_multiple_planet_diffs(self):
        stored = {"Earth": ["Moon"], "Mars": ["Phobos"]}
        live = {"Earth": ["Moon", "NewEarthMoon"], "Mars": ["Phobos", "Deimos"]}
        result = diff_language(stored, live, "EN")
        planets = [d.planet for d in result]
        self.assertIn("Earth", planets)
        self.assertIn("Mars", planets)


# ---------------------------------------------------------------------------
# Tests for diff_between_languages
# ---------------------------------------------------------------------------

class TestDiffBetweenLanguages(unittest.TestCase):
    def test_identical_lists_no_discrepancy(self):
        en = {"Mars": ["Phobos", "Deimos"]}
        cs = {"Mars": ["Phobos", "Deimos"]}
        result = diff_between_languages(en, cs)
        self.assertEqual(result, {})

    def test_extra_moon_in_en(self):
        en = {"Mars": ["Phobos", "Deimos", "UnknownMoon"]}
        cs = {"Mars": ["Phobos", "Deimos"]}
        result = diff_between_languages(en, cs)
        self.assertIn("Mars", result)
        self.assertIn("UnknownMoon", result["Mars"]["only_in_en"])
        self.assertEqual(result["Mars"]["only_in_cs"], [])

    def test_extra_moon_in_cs(self):
        en = {"Mars": ["Phobos"]}
        cs = {"Mars": ["Phobos", "Deimos"]}
        result = diff_between_languages(en, cs)
        self.assertIn("Mars", result)
        self.assertIn("Deimos", result["Mars"]["only_in_cs"])

    def test_planet_only_in_one_language(self):
        en = {"Mars": ["Phobos"], "Neptune": ["Triton"]}
        cs = {"Mars": ["Phobos"]}
        result = diff_between_languages(en, cs)
        self.assertIn("Neptune", result)

    def test_empty_dicts_no_discrepancy(self):
        result = diff_between_languages({}, {})
        self.assertEqual(result, {})

    def test_order_differences_not_flagged(self):
        """diff_between_languages ignores order; it only compares membership."""
        en = {"Mars": ["Phobos", "Deimos"]}
        cs = {"Mars": ["Deimos", "Phobos"]}
        result = diff_between_languages(en, cs)
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# Tests for load_database
# ---------------------------------------------------------------------------

class TestLoadDatabase(unittest.TestCase):
    def test_loads_valid_json(self):
        data = {"en": {"Mars": ["Phobos"]}, "cs": {}, "last_updated": "2026-01-01"}
        json_str = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=json_str)):
            result = load_database("moons.json")
        self.assertEqual(result["en"]["Mars"], ["Phobos"])

    def test_missing_file_exits_with_code_2(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            with self.assertRaises(SystemExit) as ctx:
                load_database("missing.json")
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
