"""Tests for shared.py utilities."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import format_change, safe_json_load


class TestFormatChange(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(format_change(3.5), "+3.50%")

    def test_negative(self):
        self.assertEqual(format_change(-2.1), "-2.10%")

    def test_zero(self):
        self.assertEqual(format_change(0.0), "0.00%")

    def test_none(self):
        self.assertEqual(format_change(None), "N/A")

    def test_small_positive(self):
        self.assertEqual(format_change(0.001), "+0.00%")

    def test_float_precision(self):
        self.assertEqual(format_change(1.2345), "+1.23%")


class TestSafeJsonLoad(unittest.TestCase):
    def test_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value"}, f)
            path = f.name
        try:
            result = safe_json_load(Path(path))
            self.assertEqual(result, {"key": "value"})
        finally:
            Path(path).unlink()

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json!!!")
            path = f.name
        try:
            result = safe_json_load(Path(path))
            self.assertIsNone(result)
        finally:
            Path(path).unlink()

    def test_nonexistent_file(self):
        result = safe_json_load(Path("/nonexistent/path.json"))
        self.assertIsNone(result)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = safe_json_load(Path(path))
            self.assertIsNone(result)
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
