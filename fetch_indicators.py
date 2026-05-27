#!/usr/bin/env python3
"""
009805 ETF 每日指標抓取腳本
抓取三大指標 + ETF 價格 + 前十大持股 → 存入 JSON 供後續分析
"""

import concurrent.futures
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import get_config
from shared import (
    DATA_DIR,
    yahoo_chart,
)


def compute_changes(data: list[dict]) -> dict:
    """計算 1日/1週/1月 漲跌幅"""
    if len(data) < 2:
        return {"1d": 0, "1w": 0, "1m": 0}
    latest = data[-1]["close"]
    prev = data[-2]["close"]
    chg_1d = (latest - prev) / prev * 100 if prev else 0

    # 1w: find entry closest to 7 calendar days ago
    latest_date = datetime.strptime(data[-1]["date"], "%Y-%m-%d")
    target_date = latest_date - timedelta(days=7)
    week_ago = None
    for d in data:
        d_date = datetime.strptime(d["date"], "%Y-%m-%d")
        if d_date <= target_date:
            week_ago = d["close"]
        else:
            break
    if week_ago is None:
        week_ago = data[0]["close"]
    chg_1w = (latest - week_ago) / week_ago * 100 if week_ago else 0

    month_ago = data[0]["close"]
    chg_1m = (latest - month_ago) / month_ago * 100 if month_ago else 0

    return {"1d": round(chg_1d, 2), "1w": round(chg_1w, 2), "1m": round(chg_1m, 2)}


def compute_ma(data: list[dict], period: int) -> float | None:
    """計算移動平均線"""
    closes = [d["close"] for d in data[-period:]]
    if len(closes) < period:
        return None
    return round(sum(closes) / len(closes), 2)


def fetch_all():
    """抓取所有指標"""
    cfg = get_config()

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_str = now.strftime("%Y-%m-%d")

    result = {
        "timestamp": timestamp,
        "date": date_str,
        "indicators": {},
    }

    # ---- 收集所有需要抓取的 symbol ----
    tasks = []
    tasks.append(("etf", "009805.TW", "1d", "1mo"))
    tasks.append(("tnx", "^TNX", "1d", "1mo"))
    tasks.append(("forex", "USDTWD=X", "1d", "1mo"))

    big_tech_cfg = cfg.get("big_tech", {})
    big_tech_symbols = [s["ticker"] for s in big_tech_cfg.get("symbols", [])]
    for sym in big_tech_symbols:
        tasks.append(("big_tech", sym, "1d", "1mo"))

    holdings_cfg = cfg.get("holdings", [])
    for h in holdings_cfg:
        tasks.append(("holding", h["symbol"], "1d", "1mo"))

    # ---- 並行抓取 ----
    print(f"[FETCH] 開始並行抓取 {len(tasks)} 個 symbol (max_workers=4)...")
    results_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for category, sym, interval, range_ in tasks:
            future = executor.submit(yahoo_chart, sym, interval, range_)
            futures[future] = (category, sym)
        for future in concurrent.futures.as_completed(futures):
            category, sym = futures[future]
            try:
                results_map[sym] = future.result()
            except Exception as e:
                print(f"[ERROR] {sym}: {e}", file=sys.stderr)
                results_map[sym] = None

    # ---- 組合結果 ----
    # ETF
    etf = results_map.get("009805.TW")
    if etf and etf.get("data"):
        result["etf"] = {
            "name": "新光美國電力基建",
            "ticker": "009805.TW",
            "price": etf.get("regularMarketPrice"),
            "previousClose": etf.get("previousClose"),
            "52w_high": etf.get("fiftyTwoWeekHigh"),
            "52w_low": etf.get("fiftyTwoWeekLow"),
            "changes": compute_changes(etf.get("data", [])),
            "ma5": compute_ma(etf.get("data", []), 5),
            "ma20": compute_ma(etf.get("data", []), 20),
            "last_20_days": [
                {"date": d["date"], "close": d["close"], "volume": d.get("volume", 0)}
                for d in etf.get("data", [])[-20:]
            ],
        }

    # 10Y
    tnx = results_map.get("^TNX")
    if tnx and tnx.get("data"):
        result["indicators"]["treasury_10y"] = {
            "name": "US 10Y Treasury Yield",
            "symbol": "^TNX",
            "current": tnx.get("regularMarketPrice"),
            "previousClose": tnx.get("previousClose"),
            "changes": compute_changes(tnx.get("data", [])),
            "last_10_days": [
                {"date": d["date"], "close": d["close"]}
                for d in tnx.get("data", [])[-10:]
            ],
        }

    # Big Tech
    big_tech = {}
    for sym in big_tech_symbols:
        data = results_map.get(sym)
        if data and data.get("data"):
            changes = compute_changes(data.get("data", []))
            big_tech[sym] = {
                "price": data.get("regularMarketPrice"),
                "52w_high": data.get("fiftyTwoWeekHigh"),
                "changes": changes,
            }
    if big_tech:
        avg_1w = sum(v["changes"]["1w"] for v in big_tech.values()) / len(big_tech)
        avg_1m = sum(v["changes"]["1m"] for v in big_tech.values()) / len(big_tech)
        result["indicators"]["big_tech"] = {
            "name": "Big Tech Capex Proxy",
            "stocks": big_tech,
            "composite_1w": round(avg_1w, 2),
            "composite_1m": round(avg_1m, 2),
        }

    # Forex
    forex = results_map.get("USDTWD=X")
    if forex and forex.get("data"):
        result["indicators"]["forex"] = {
            "name": "USD/TWD",
            "symbol": "USDTWD=X",
            "current": forex.get("regularMarketPrice"),
            "previousClose": forex.get("previousClose"),
            "52w_high": forex.get("fiftyTwoWeekHigh"),
            "52w_low": forex.get("fiftyTwoWeekLow"),
            "changes": compute_changes(forex.get("data", [])),
            "last_10_days": [
                {"date": d["date"], "close": d["close"]}
                for d in forex.get("data", [])[-10:]
            ],
        }

    # Holdings
    holdings_data = []
    for h in holdings_cfg:
        sym = h["symbol"]
        name = h["name"]
        weight = h["weight"]
        data = results_map.get(sym)
        if data and data.get("data"):
            changes = compute_changes(data.get("data", []))
            holdings_data.append({
                "symbol": sym,
                "name": name,
                "weight": weight,
                "price": data.get("regularMarketPrice"),
                "changes": changes,
            })

    total_1w = sum(h["weight"] * h["changes"]["1w"] for h in holdings_data) / 100
    total_1m = sum(h["weight"] * h["changes"]["1m"] for h in holdings_data) / 100

    result["holdings"] = {
        "stocks": holdings_data,
        "weighted_contribution_1w": round(total_1w, 2),
        "weighted_contribution_1m": round(total_1m, 2),
    }

    # ---- 綜合訊號 ----
    result["signals"] = compute_signals(result, cfg)

    # 儲存（含去重檢查）
    # 每日檔案：若已存在則跳過，避免重複抓取
    daily_file = DATA_DIR / f"{date_str}.json"
    if daily_file.exists():
        print(f"[SKIP] 今日資料已存在 {daily_file}，不重複寫入")
    else:
        with open(daily_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ 資料已儲存至 {daily_file}")

    # 附加到歷史彙總檔：只讀最後一行檢查今日是否已存在（append-only）
    summary = {
        "date": date_str,
        "etf_price": result.get("etf", {}).get("price"),
        "etf_change_1d": result.get("etf", {}).get("changes", {}).get("1d"),
        "treasury_10y": result.get("indicators", {}).get("treasury_10y", {}).get("current"),
        "usdtwd": result.get("indicators", {}).get("forex", {}).get("current"),
        "big_tech_composite_1w": result.get("indicators", {}).get("big_tech", {}).get("composite_1w"),
        "big_tech_composite_1m": result.get("indicators", {}).get("big_tech", {}).get("composite_1m"),
        "signal": result.get("signals", {}).get("overall"),
    }
    history_file = DATA_DIR / "history.jsonl"
    already_exists = False
    if history_file.exists():
        with open(history_file, "rb") as f:
            try:
                f.seek(-2, 2)
                while f.read(1) != b"\n":
                    f.seek(-2, 1)
            except OSError:
                f.seek(0)
            last_line = f.readline().decode("utf-8").strip()
            if last_line:
                try:
                    entry = json.loads(last_line)
                    if entry.get("date") == date_str:
                        already_exists = True
                except json.JSONDecodeError:
                    pass
    if already_exists:
        print(f"[SKIP] 今日記錄已存在於 {history_file}，不重複追加")
    else:
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        print(f"📊 歷史記錄追加至 {history_file}")

    return result


def compute_signals(result: dict, cfg: dict) -> dict:
    """根據三大指標計算綜合訊號（閾值從 config 載入）"""
    signals = {}

    # 讀取閾值
    tnx_th = cfg.get("treasury", {}).get("thresholds", {})
    bt_th = cfg.get("big_tech", {}).get("thresholds", {})
    fx_th = cfg.get("forex", {}).get("thresholds", {})

    # 1. 殖利率
    tnx = result.get("indicators", {}).get("treasury_10y", {})
    if tnx:
        current = tnx.get("current", 0)
        bullish = tnx_th.get("bullish", 4.30)
        neutral_high = tnx_th.get("neutral_high", 4.60)
        bearish = tnx_th.get("bearish", 4.80)
        if current and current < bullish:
            signals["treasury"] = f"🟢 利多（<{bullish}%）"
        elif current and current < neutral_high:
            signals["treasury"] = f"🟡 中性（{bullish}-{neutral_high}%）"
        elif current and current >= bearish:
            signals["treasury"] = f"🔴 利空（>{bearish}%）"
        else:
            signals["treasury"] = f"🟠 偏空（{neutral_high}-{bearish}%）"

    # 2. Big Tech
    bt = result.get("indicators", {}).get("big_tech", {})
    if bt:
        c1m = bt.get("composite_1m", 0)
        bt_bullish = bt_th.get("bullish", 5.0)
        bt_bearish = bt_th.get("bearish", -10.0)
        if c1m > bt_bullish:
            signals["big_tech"] = f"🟢 強勁（月漲 >{bt_bullish}%）"
        elif c1m >= 0:
            signals["big_tech"] = "🟡 穩健（月漲 0-5%）"
        elif c1m > bt_bearish:
            signals["big_tech"] = f"🟠 轉弱（月跌 0-{abs(bt_bearish)}%）"
        else:
            signals["big_tech"] = f"🔴 危險（月跌 >{abs(bt_bearish)}%）"

    # 3. 匯率
    fx = result.get("indicators", {}).get("forex", {})
    if fx:
        current = fx.get("current", 0)
        fx_bullish = fx_th.get("bullish", 32.0)
        fx_neutral_low = fx_th.get("neutral_low", 30.5)
        if current and current > fx_bullish:
            signals["forex"] = "🟢 台幣貶值（有利）"
        elif current and current > fx_neutral_low:
            signals["forex"] = f"🟡 中性（{fx_neutral_low}-{fx_bullish}）"
        else:
            signals["forex"] = "🔴 台幣強勢（不利）"

    # 4. 綜合
    bullish = sum(1 for v in signals.values() if "🟢" in v)
    bearish = sum(1 for v in signals.values() if "🔴" in v)
    if bullish >= 2 and bearish == 0:
        signals["overall"] = "🟢 偏多"
    elif bearish >= 2 and bullish == 0:
        signals["overall"] = "🔴 偏空"
    elif bullish == bearish:
        signals["overall"] = "🟡 中性觀望"
    elif bullish > bearish:
        signals["overall"] = "🟢 中性偏多"
    else:
        signals["overall"] = "🔴 中性偏空"

    return signals


if __name__ == "__main__":
    result = fetch_all()
    # Print summary — all dict[key] → .get() for safety
    print("\n" + "=" * 50)
    print("📡 009805 每日指標摘要")
    print("=" * 50)
    etf = result.get("etf", {})
    etf_chg = etf.get("changes", {})
    indicators = result.get("indicators", {})
    print(
        f"ETF 價格：{etf.get('price', 'N/A')} "
        f"({etf_chg.get('1d', 'N/A')})"
    )
    print(
        f"10Y 殖利率："
        f"{indicators.get('treasury_10y', {}).get('current', 'N/A')}%"
    )
    print(
        f"USD/TWD："
        f"{indicators.get('forex', {}).get('current', 'N/A')}"
    )
    bt_c1m = indicators.get("big_tech", {}).get("composite_1m", "N/A")
    print(f"Big Tech 綜合月變動：{bt_c1m}")
    print(
        f"\n綜合訊號："
        f"{result.get('signals', {}).get('overall', 'N/A')}"
    )
    for k, v in result.get("signals", {}).items():
        if k != "overall":
            print(f"  {k}: {v}")
