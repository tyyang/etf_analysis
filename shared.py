#!/usr/bin/env python3
"""
009805 ETF 監控系統 — 共用模組
提供路徑常數、設定載入、格式化函數、Yahoo Finance API 封裝
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---- 路徑常數 ----
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

# ---- HTTP ----
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
TIMEOUT = 15
RATE_LIMIT_SLEEP = 1.5

# ---- 設定快取 ----
_config = None


def load_config() -> dict:
    """載入 config.yaml（帶快取）"""
    global _config
    if _config is None:
        config_path = ROOT / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def safe_json_load(filepath: Path) -> dict | None:
    """安全載入 JSON 檔案，失敗時回傳 None 並記錄錯誤"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] 無法讀取 {filepath}: {e}", file=sys.stderr)
        return None


def format_change(value: float | None) -> str:
    """格式化漲跌幅字串"""
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def yahoo_chart(
    symbol: str, interval: str = "1d", range_: str = "1mo", retries: int = 3
) -> dict | None:
    """抓取 Yahoo Finance chart API 資料，含重試、速率限制與防禦性取值"""
    time.sleep(RATE_LIMIT_SLEEP)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?interval={interval}&range={range_}"
    )
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read())

            # 防禦性取值：chart → result[0]
            chart = data.get("chart") or {}
            results = chart.get("result")
            if not results or len(results) == 0:
                print(f"[WARN] {symbol}: no chart result", file=sys.stderr)
                return None
            result = results[0]

            meta = result.get("meta", {})

            # 防禦性取值：indicators → quote[0]
            indicators = result.get("indicators") or {}
            quotes = indicators.get("quote")
            if not quotes or len(quotes) == 0:
                print(f"[WARN] {symbol}: no quote data", file=sys.stderr)
                return None
            quote = quotes[0]

            timestamps = result.get("timestamp", [])
            closes = quote.get("close", [])
            volumes = quote.get("volume", [])

            valid = [
                (t, c, v)
                for t, c, v in zip(timestamps, closes, volumes)
                if c is not None
            ]

            return {
                "symbol": symbol,
                "currency": meta.get("currency", "N/A"),
                "regularMarketPrice": meta.get("regularMarketPrice"),
                "previousClose": meta.get("previousClose"),
                "fiftyTwoWeekHigh": meta.get("fiftyTwoWeekHigh"),
                "fiftyTwoWeekLow": meta.get("fiftyTwoWeekLow"),
                "data": [
                    {
                        "date": datetime.fromtimestamp(t, tz=timezone.utc).strftime(
                            "%Y-%m-%d"
                        ),
                        "close": c,
                        "volume": v,
                    }
                    for t, c, v in valid
                ],
            }
        except Exception as e:
            if attempt < retries - 1:
                backoff = 2 ** attempt  # exponential: 1s, 2s, 4s
                print(
                    f"[RETRY] {symbol}: {e}, retrying in {backoff}s "
                    f"({attempt + 2}/{retries})...",
                    file=sys.stderr,
                )
                time.sleep(backoff)
            else:
                print(f"[ERROR] {symbol}: {e}", file=sys.stderr)
                return None
    return None
