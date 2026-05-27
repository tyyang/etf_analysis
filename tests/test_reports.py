"""Tests for report generation functions."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daily_report import generate_daily
from weekly_analysis import generate_weekly
from quarterly_analysis import generate_quarterly


def _make_daily_data(overrides=None):
    """Build realistic daily data dict for report generation."""
    data = {
        "timestamp": "2026-05-27T12:00:00Z",
        "date": "2026-05-27",
        "etf": {
            "name": "新光美國電力基建",
            "ticker": "009805.TW",
            "price": 16.50,
            "previousClose": 16.30,
            "52w_high": 17.80,
            "52w_low": 13.50,
            "changes": {"1d": 1.23, "1w": 2.50, "1m": 5.00},
            "ma5": 16.20,
            "ma20": 15.80,
            "last_20_days": [
                {"date": "2026-05-20", "close": 16.00, "volume": 500000},
                {"date": "2026-05-27", "close": 16.50, "volume": 800000},
            ],
        },
        "indicators": {
            "treasury_10y": {
                "name": "US 10Y Treasury Yield",
                "symbol": "^TNX",
                "current": 4.35,
                "previousClose": 4.40,
                "changes": {"1d": 1.10, "1w": 5.00, "1m": 10.00},
                "last_10_days": [
                    {"date": "2026-05-20", "close": 4.40},
                    {"date": "2026-05-27", "close": 4.35},
                ],
            },
            "big_tech": {
                "name": "Big Tech Capex Proxy",
                "stocks": {
                    "GOOGL": {
                        "price": 180.0,
                        "52w_high": 200.0,
                        "changes": {"1d": 0.5, "1w": 2.0, "1m": 8.0},
                    }
                },
                "composite_1w": 2.0,
                "composite_1m": 8.0,
            },
            "forex": {
                "name": "USD/TWD",
                "symbol": "USDTWD=X",
                "current": 31.80,
                "previousClose": 31.60,
                "52w_high": 33.50,
                "52w_low": 29.00,
                "changes": {"1d": 0.63, "1w": 1.50, "1m": 3.00},
                "last_10_days": [],
            },
        },
        "holdings": {
            "stocks": [
                {
                    "symbol": "GEV",
                    "name": "GE Vernova",
                    "weight": 13.23,
                    "price": 250.0,
                    "changes": {"1d": 1.0, "1w": 3.0, "1m": 10.0},
                }
            ]
        },
        "signals": {
            "treasury": "🟢 利多（<4.3%）",
            "big_tech": "🟢 強勁（月漲 >5.0%）",
            "forex": "🟡 中性（30.5-32.0）",
            "overall": "🟢 中性偏多",
        },
    }
    if overrides:
        data.update(overrides)
    return data


class TestGenerateDaily(unittest.TestCase):
    def test_output_contains_key_sections(self):
        data = _make_daily_data()
        report = generate_daily(data)
        self.assertIn("009805 每日追蹤報告", report)
        self.assertIn("ETF 報價", report)
        self.assertIn("三大指標", report)
        self.assertIn("前十大持股", report)
        self.assertIn("今日操作建議", report)
        self.assertIn("不構成投資建議", report)

    def test_output_contains_price(self):
        data = _make_daily_data()
        report = generate_daily(data)
        self.assertIn("16.5", report)
        self.assertIn("+1.23%", report)

    def test_bearish_signal_output(self):
        data = _make_daily_data()
        data["signals"]["overall"] = "🔴 偏空"
        report = generate_daily(data)
        self.assertIn("🔴 偏空", report)

    def test_missing_holdings(self):
        data = _make_daily_data()
        data["holdings"]["stocks"] = []
        report = generate_daily(data)
        self.assertIn("前十大持股", report)

    def test_no_history(self):
        data = _make_daily_data()
        data["etf"]["last_20_days"] = []
        report = generate_daily(data)
        self.assertNotIn("近 20 日走勢", report)


class TestGenerateWeekly(unittest.TestCase):
    def test_output_contains_key_sections(self):
        data_list = [_make_daily_data() for _ in range(5)]
        report = generate_weekly(data_list)
        self.assertIn("每週分析策略報告", report)
        self.assertIn("週度摘要", report)
        self.assertIn("每日快照", report)
        self.assertIn("下週操作策略", report)
        self.assertIn("不構成投資建議", report)

    def test_empty_list(self):
        report = generate_weekly([])
        self.assertIn("無可用數據", report)

    def test_single_day(self):
        data_list = [_make_daily_data()]
        report = generate_weekly(data_list)
        self.assertIn("每週分析策略報告", report)
        self.assertIn("持平", report)

    def test_trend_rising(self):
        up_data = _make_daily_data()
        up_data["etf"]["price"] = 17.0
        data_list = [_make_daily_data() for _ in range(4)] + [up_data]
        report = generate_weekly(data_list)
        self.assertIn("每週分析策略報告", report)


class TestGenerateQuarterly(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_data_file(self, date_str, price, tnx_val=4.35):
        data = _make_daily_data()
        data["date"] = date_str
        data["etf"]["price"] = price
        data["indicators"]["treasury_10y"]["current"] = tnx_val
        filepath = self.data_dir / f"{date_str}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return filepath

    def test_single_file(self):
        fp = self._write_data_file("2026-05-20", 16.0)
        report = generate_quarterly([fp])
        self.assertIn("每季分析策略報告", report)
        self.assertIn("季度績效摘要", report)
        self.assertIn("不構成投資建議", report)

    def test_empty_files(self):
        report = generate_quarterly([])
        self.assertIn("無可用數據", report)

    def test_multi_month(self):
        f1 = self._write_data_file("2026-05-20", 16.0)
        f2 = self._write_data_file("2026-05-27", 16.5)
        f3 = self._write_data_file("2026-06-01", 17.0)
        report = generate_quarterly([f1, f2, f3])
        self.assertIn("每季分析策略報告", report)
        self.assertIn("月均價格走勢", report)

    def test_volatility_with_enough_data(self):
        files = [self._write_data_file(f"2026-05-{20+i:02d}", 16.0 + i * 0.1) for i in range(12)]
        report = generate_quarterly(files)
        self.assertIn("年化波動率", report)

    def test_corrupted_file_skipped(self):
        _ = self._write_data_file("2026-05-20", 16.0)
        bad_file = self.data_dir / "2026-05-21.json"
        bad_file.write_text("not json", encoding="utf-8")
        report = generate_quarterly([bad_file, self.data_dir / "2026-05-20.json"])
        self.assertIn("每季分析策略報告", report)


if __name__ == "__main__":
    unittest.main()
