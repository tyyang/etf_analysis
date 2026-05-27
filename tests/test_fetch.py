"""Tests for fetch_indicators.py utility functions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_indicators import compute_changes, compute_ma, compute_signals


def _make_price_data(closes: list[float]) -> list[dict]:
    """Helper: build data list in shared.yahoo_chart return format."""
    out = []
    for i, c in enumerate(closes):
        out.append({"date": f"2026-05-{20+i:02d}", "close": c, "volume": 100000})
    return out


class TestComputeChanges(unittest.TestCase):
    def test_single_day(self):
        data = _make_price_data([100])
        result = compute_changes(data)
        self.assertEqual(result, {"1d": 0, "1w": 0, "1m": 0})

    def test_two_days_up(self):
        data = _make_price_data([100, 110])
        result = compute_changes(data)
        self.assertEqual(result["1d"], 10.0)
        self.assertEqual(result["1w"], 10.0)
        self.assertEqual(result["1m"], 10.0)

    def test_two_days_down(self):
        data = _make_price_data([100, 90])
        result = compute_changes(data)
        self.assertEqual(result["1d"], -10.0)

    def test_multi_day(self):
        data = _make_price_data([100, 102, 101, 104, 106, 105])
        result = compute_changes(data)
        # 1d: 105 -> 106 is wrong. Last two: 106, 105
        # Actually: data[-1].close = 105, data[-2].close = 106
        # 1d = (105-106)/106*100 = -0.94...
        self.assertAlmostEqual(result["1d"], -0.94, places=1)
        # 1m: (105-100)/100*100 = 5.0
        self.assertAlmostEqual(result["1m"], 5.0, places=1)


class TestComputeMA(unittest.TestCase):
    def test_normal(self):
        data = _make_price_data([10, 20, 30, 40, 50])
        result = compute_ma(data, 3)
        self.assertEqual(result, 40.0)

    def test_insufficient_data(self):
        data = _make_price_data([10, 20])
        result = compute_ma(data, 5)
        self.assertIsNone(result)

    def test_exact_period(self):
        data = _make_price_data([10, 20, 30])
        result = compute_ma(data, 3)
        self.assertEqual(result, 20.0)

    def test_more_than_period(self):
        data = _make_price_data([1, 2, 3, 4, 5, 6])
        result = compute_ma(data, 3)
        self.assertEqual(result, 5.0)


class TestComputeSignals(unittest.TestCase):
    def _make_result(self, tnx_current=None, bt_composite_1m=None, fx_current=None):
        result = {"indicators": {}, "etf": {}}
        if tnx_current is not None:
            result["indicators"]["treasury_10y"] = {
                "name": "10Y",
                "symbol": "^TNX",
                "current": tnx_current,
                "previousClose": None,
                "changes": {"1d": 0, "1w": 0, "1m": 0},
                "last_10_days": [],
            }
        if bt_composite_1m is not None:
            result["indicators"]["big_tech"] = {
                "stocks": {},
                "composite_1w": 0,
                "composite_1m": bt_composite_1m,
            }
        if fx_current is not None:
            result["indicators"]["forex"] = {
                "name": "USD/TWD",
                "current": fx_current,
                "previousClose": None,
                "changes": {"1d": 0, "1w": 0, "1m": 0},
                "last_10_days": [],
            }
        return result

    def _cfg(self):
        return {
            "treasury": {"thresholds": {"bullish": 4.30, "neutral_high": 4.60, "bearish": 4.80}},
            "big_tech": {"thresholds": {"bullish": 5.0, "bearish": -10.0}},
            "forex": {"thresholds": {"bullish": 32.0, "neutral_low": 30.5}},
        }

    def test_bullish_overall(self):
        result = self._make_result(tnx_current=4.0, bt_composite_1m=6.0, fx_current=33.0)
        signals = compute_signals(result, self._cfg())
        self.assertIn("overall", signals)
        self.assertIn("🟢", signals["overall"])

    def test_bearish_overall(self):
        result = self._make_result(tnx_current=5.0, bt_composite_1m=-15.0, fx_current=29.0)
        signals = compute_signals(result, self._cfg())
        self.assertIn("overall", signals)
        self.assertIn("🔴", signals["overall"])

    def test_neutral_overall(self):
        result = self._make_result(tnx_current=4.50, bt_composite_1m=2.0, fx_current=31.0)
        signals = compute_signals(result, self._cfg())
        self.assertIn("overall", signals)
        self.assertIn("🟡", signals["overall"])

    def test_missing_indicators(self):
        result = self._make_result()
        signals = compute_signals(result, self._cfg())
        self.assertEqual(signals["overall"], "🟡 中性觀望")

    def test_treasury_bullish(self):
        result = self._make_result(tnx_current=4.0)
        signals = compute_signals(result, self._cfg())
        self.assertIn("treasury", signals)
        self.assertIn("🟢", signals["treasury"])

    def test_treasury_neutral(self):
        result = self._make_result(tnx_current=4.50)
        signals = compute_signals(result, self._cfg())
        self.assertIn("treasury", signals)
        self.assertIn("🟡", signals["treasury"])

    def test_treasury_bearish(self):
        result = self._make_result(tnx_current=5.00)
        signals = compute_signals(result, self._cfg())
        self.assertIn("treasury", signals)
        self.assertIn("🔴", signals["treasury"])

    def test_forex_bullish(self):
        result = self._make_result(fx_current=33.0)
        signals = compute_signals(result, self._cfg())
        self.assertIn("forex", signals)
        self.assertIn("🟢", signals["forex"])

    def test_forex_bearish(self):
        result = self._make_result(fx_current=29.0)
        signals = compute_signals(result, self._cfg())
        self.assertIn("forex", signals)
        self.assertIn("🔴", signals["forex"])


if __name__ == "__main__":
    unittest.main()
