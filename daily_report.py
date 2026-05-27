#!/usr/bin/env python3
"""
009805 ETF 每日追蹤報告
讀取當日 JSON → 生成 Markdown 報告 → 輸出到 reports/ 目錄
"""

import sys
from datetime import datetime, timezone

from config import get_config
from shared import DATA_DIR, REPORT_DIR, format_change, safe_json_load


def load_latest_data() -> dict | None:
    """載入最新數據"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = DATA_DIR / f"{today}.json"

    if not filepath.exists():
        files = sorted(DATA_DIR.glob("*.json"))
        if not files:
            print("[ERROR] 無可用數據，請先執行 fetch_indicators.py", file=sys.stderr)
            return None
        filepath = files[-1]
        print(f"[INFO] 使用最新數據: {filepath}")

    return safe_json_load(filepath)


def generate_daily(data: dict) -> str:
    """生成每日報告"""
    cfg = get_config()
    position_cfg = cfg.get("position", {})
    tech_cfg = cfg.get("technical", {})

    etf = data.get("etf", {})
    indicators = data.get("indicators", {})
    holdings = data.get("holdings", {}).get("stocks", [])
    signals = data.get("signals", {})

    report = f"""# 📡 009805 每日追蹤報告

> **日期：{data.get('date', 'N/A')}**｜綜合訊號：**{signals.get('overall', 'N/A')}**

---

## 💰 ETF 報價

| 指標 | 數值 |
|------|------|
| 收盤價 | **{etf.get('price', 'N/A')}** |
| 前日收盤 | {etf.get('previousClose', 'N/A')} |
| 52 週高 | {etf.get('52w_high', 'N/A')} |
| 52 週低 | {etf.get('52w_low', 'N/A')} |
| 5 日均線 | {etf.get('ma5', 'N/A')} |
| 20 日均線 | {etf.get('ma20', 'N/A')} |
| 日漲跌 | {format_change(etf.get('changes', {}).get('1d'))} |
| 週漲跌 | {format_change(etf.get('changes', {}).get('1w'))} |
| 月漲跌 | {format_change(etf.get('changes', {}).get('1m'))} |

"""

    # ---- 三大指標 ----
    report += "---\n\n## 🔭 三大指標\n\n"

    # 指標一：10Y
    tnx = indicators.get("treasury_10y", {})
    report += f"""### ① 美國 10 年期公債殖利率：**{tnx.get('current', 'N/A')}%** {signals.get('treasury', '')}

| 日變動 | 週變動 | 月變動 |
|--------|--------|--------|
| {format_change(tnx.get('changes', {}).get('1d'))} | {format_change(tnx.get('changes', {}).get('1w'))} | {format_change(tnx.get('changes', {}).get('1m'))} |

"""

    # 指標二：Big Tech
    bt = indicators.get("big_tech", {})
    bt_stocks = bt.get("stocks", {})
    report += f"""### ② 大型科技股 Capex 代理：綜合月變動 **{format_change(bt.get('composite_1m'))}** {signals.get('big_tech', '')}

| 股票 | 股價 | 日 | 週 | 月 |
|------|------|----|----|-----|
"""
    for sym, info in bt_stocks.items():
        chg = info.get("changes", {})
        report += f"| {sym} | ${info.get('price', 'N/A')} | {format_change(chg.get('1d'))} | {format_change(chg.get('1w'))} | {format_change(chg.get('1m'))} |\n"

    # 指標三：匯率
    fx = indicators.get("forex", {})
    report += f"""
### ③ USD/TWD 匯率：**{fx.get('current', 'N/A')}** {signals.get('forex', '')}

| 日變動 | 週變動 | 月變動 | 52 週高 | 52 週低 |
|--------|--------|--------|---------|---------|
| {format_change(fx.get('changes', {}).get('1d'))} | {format_change(fx.get('changes', {}).get('1w'))} | {format_change(fx.get('changes', {}).get('1m'))} | {fx.get('52w_high', 'N/A')} | {fx.get('52w_low', 'N/A')} |

"""

    # ---- 前十大持股 ----
    report += "---\n\n## 🏭 前十大持股漲跌\n\n"
    report += "| 持股 | 權重 | 股價 | 日 | 週 | 月 |\n"
    report += "|------|------|------|----|----|----|\n"
    for h in holdings:
        chg = h.get("changes", {})
        report += f"| {h.get('name', '?')} ({h.get('symbol', '?')}) | {h.get('weight', 0)}% | ${h.get('price', 'N/A')} | {format_change(chg.get('1d'))} | {format_change(chg.get('1w'))} | {format_change(chg.get('1m'))} |\n"

    # ---- 近 20 日走勢 ----
    history = etf.get("last_20_days", [])
    if history:
        report += "\n---\n\n## 📈 近 20 日走勢\n\n"
        report += "```\n"
        for d in history:
            close = d["close"]
            vol = d.get("volume", 0) or 0
            bar_len = min(int(vol / 500000), 60)
            bar = "█" * bar_len
            report += f"{d['date']}  {close:>6.2f}  {bar}\n"
        report += "```\n"

    # ---- 策略建議 ----
    report += "\n---\n\n## 🎯 今日操作建議\n\n"

    price = etf.get("price", 0) or 0
    chg_1d = etf.get("changes", {}).get("1d", 0) or 0
    ma5 = etf.get("ma5", 0) or 0
    ma20 = etf.get("ma20", 0) or 0

    suggestions = []
    reduce_alert = position_cfg.get("reduce_alert")
    if price and reduce_alert and price >= reduce_alert:
        suggestions.append(f"⚠️ 價格 ${price} 已達減碼警戒線 ${reduce_alert}，追高風險大，建議觀望或減碼")
    if ma5 and ma20 and price:
        if price > ma5 > ma20:
            suggestions.append("📈 短線多頭排列（價 > 5MA > 20MA），持有者續抱")
        elif price < ma5 < ma20:
            suggestions.append("📉 短線空頭排列，等待止穩訊號再進場")
    if abs(chg_1d) > 2:
        suggestions.append(f"⚡ 今日波動 {chg_1d:+.2f}%，超過 2%，注意是否有重大事件驅動")

    overall = signals.get("overall", "")
    if "🟢" in overall:
        suggestions.append("🟢 綜合訊號偏多，可考慮逢回建立小倉位")
    elif "🔴" in overall:
        suggestions.append("🔴 綜合訊號偏空，建議觀望或減碼")
    else:
        suggestions.append("🟡 訊號中性，等待更明確方向")

    if not suggestions:
        suggestions.append("維持觀望，等待指標進一步明朗")

    for s in suggestions:
        report += f"- {s}\n"

    report += f"""
> ⚠️ 本報告為自動生成，僅供參考，不構成投資建議。
> 產生時間：{data.get('timestamp', 'N/A')}
"""
    return report


def main():
    data = load_latest_data()
    if not data:
        return

    report = generate_daily(data)
    date_str = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    output_file = REPORT_DIR / f"daily_{date_str}.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 每日報告已產生：{output_file}")
    print(report)


if __name__ == "__main__":
    main()
