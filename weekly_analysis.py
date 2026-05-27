#!/usr/bin/env python3
"""
009805 ETF 每週分析策略報告
讀取過去 5-7 天的每日數據 → 週趨勢分析 → 生成策略建議
"""

import statistics
import sys
from datetime import datetime, timezone

from config import get_config
from shared import DATA_DIR, REPORT_DIR, format_change, safe_json_load

config = get_config()


def load_week_data(days: int = 7) -> list[dict]:
    """載入過去 N 天的數據"""
    files = sorted(DATA_DIR.glob("20*.json"))
    if not files:
        print("[ERROR] 無可用數據", file=sys.stderr)
        return []

    # 取最近 days 個檔案
    recent = files[-days:]
    data = []
    for f in recent:
        d = safe_json_load(f)
        if d is not None:
            data.append(d)
    return data


def generate_weekly(data_list: list[dict]) -> str:
    """生成每週分析報告"""
    if not data_list:
        return "# 無可用數據"

    latest = data_list[-1]
    first = data_list[0]
    etf_latest = latest.get("etf", {})
    etf_first = first.get("etf", {})

    price_now = etf_latest.get("price") or 0
    price_week_ago = etf_first.get("price") or 0
    week_chg = ((price_now - price_week_ago) / price_week_ago * 100) if price_week_ago else 0

    date_end = latest.get("date", "N/A")
    date_start = first.get("date", "N/A")

    # 提取每日摘要
    daily_summary = []
    for d in data_list:
        etf = d.get("etf", {})
        tnx = d.get("indicators", {}).get("treasury_10y", {})
        fx = d.get("indicators", {}).get("forex", {})
        sig = d.get("signals", {}).get("overall", "")
        daily_summary.append({
            "date": d.get("date", ""),
            "price": etf.get("price"),
            "chg": etf.get("changes", {}).get("1d"),
            "tnx": tnx.get("current"),
            "usdtwd": fx.get("current"),
            "signal": sig,
        })

    # 判斷趨勢方向
    prices = [s["price"] for s in daily_summary if s["price"]]

    # 趨勢判斷
    if len(prices) >= 5:
        first_half = sum(prices[:len(prices)//2]) / (len(prices)//2)
        second_half = sum(prices[len(prices)//2:]) / (len(prices) - len(prices)//2)
        trend = "📈 上升" if second_half > first_half else "📉 下跌"
    else:
        trend = "⚪ 持平"

    # 波動率（標準差）
    if len(prices) >= 3:
        avg = sum(prices) / len(prices)
        if avg > 0:
            volatility = statistics.stdev(prices) / avg * 100
        else:
            volatility = 0
    else:
        volatility = 0

    # 訊號統計
    bullish_days = sum(1 for s in daily_summary if "🟢" in (s.get("signal") or ""))
    bearish_days = sum(1 for s in daily_summary if "🔴" in (s.get("signal") or ""))

    report = f"""# 📊 009805 每週分析策略報告

> **區間：{date_start} → {date_end}**｜交易日數：{len(data_list)} 天

---

## 📈 週度摘要

| 指標 | 數值 |
|------|------|
| 週初價格 | {price_week_ago} |
| 週末價格 | **{price_now}** |
| 週漲跌 | **{week_chg:+.2f}%** |
| 趨勢方向 | {trend} |
| 週波動率 | {volatility:.1f}% |
| 多頭天數 | {bullish_days} 天 |
| 空頭天數 | {bearish_days} 天 |

---

## 📅 每日快照

| 日期 | ETF | 日變動 | 10Y | USD/TWD | 訊號 |
|------|-----|--------|-----|---------|------|
"""
    for s in daily_summary:
        chg_str = format_change(s["chg"])
        report += f"| {s['date'][-5:]} | {s.get('price', 'N/A')} | {chg_str} | {s.get('tnx', 'N/A')}% | {s.get('usdtwd', 'N/A')} | {s.get('signal', '')} |\n"

    # ---- 三大指標週分析 ----
    report += "\n---\n\n## 🔭 三大指標週變化\n\n"

    # 10Y
    tnx_latest = latest.get("indicators", {}).get("treasury_10y", {})
    tnx_first_val = first.get("indicators", {}).get("treasury_10y", {})
    tnx_now = tnx_latest.get("current", 0) or 0
    tnx_prev = tnx_first_val.get("current", 0) or 0
    tnx_wk = tnx_now - tnx_prev if tnx_now and tnx_prev else 0
    tnx_bp = tnx_wk * 100  # convert to basis points
    tnx_threshold = config.get("treasury", {}).get("alert_change_1w", 0.10)

    report += f"""### ① 10Y 公債殖利率：{tnx_now:.2f}%（週變動 {tnx_bp:+.0f} bp）

"""
    if tnx_wk < -tnx_threshold:
        report += f"> 🟢 殖利率下行 >{tnx_threshold*100:.0f}bp，公用事業估值受惠\n\n"
    elif tnx_wk > tnx_threshold:
        report += f"> 🔴 殖利率上行 >{tnx_threshold*100:.0f}bp，公用事業承壓\n\n"

    # Big Tech
    bt = latest.get("indicators", {}).get("big_tech", {})
    bt_composite = bt.get("composite_1w", 0)
    report += f"""### ② Big Tech Capex 代理：週綜合 {format_change(bt_composite)}

| 股票 | 週變動 |
|------|--------|
"""
    for sym, info in bt.get("stocks", {}).items():
        chg = info.get("changes", {}).get("1w", 0)
        report += f"| {sym} | {format_change(chg)} |\n"

    # 匯率
    fx = latest.get("indicators", {}).get("forex", {})
    fx_now = fx.get("current", 0) or 0
    fx_first_val = first.get("indicators", {}).get("forex", {})
    fx_prev = fx_first_val.get("current", 0) or 0
    fx_wk = fx_now - fx_prev if fx_now and fx_prev else 0
    fx_threshold = config.get("forex", {}).get("alert_change_1w", 0.30)

    report += f"""
### ③ USD/TWD：{fx_now:.2f}（週變動 {fx_wk:+.2f} 角）

"""
    if fx_wk < -fx_threshold:
        report += f"> 🔴 台幣升值 >{fx_threshold*10:.0f} 角，匯損壓力增加\n\n"
    elif fx_wk > fx_threshold:
        report += f"> 🟢 台幣貶值 >{fx_threshold*10:.0f} 角，匯兌收益\n\n"

    # ---- 持股分析 ----
    holdings = latest.get("holdings", {}).get("stocks", [])
    if holdings:
        report += "---\n\n## 🏭 主要持股週表現\n\n"
        report += "| 持股 | 權重 | 週變動 | 貢獻度 |\n"
        report += "|------|------|--------|--------|\n"
        for h in holdings:
            chg = h.get("changes", {}).get("1w", 0) or 0
            contrib = (h.get("weight", 0) or 0) * chg / 100
            report += f"| {h.get('name', '?')} ({h.get('symbol', '?')}) | {h.get('weight', 0)}% | {format_change(chg)} | {contrib:+.2f}% |\n"

    # ---- 策略建議（四個情境分支） ----
    report += "\n---\n\n## 🎯 下週操作策略\n\n"

    # 根據週趨勢給建議
    signals = latest.get("signals", {})
    overall = signals.get("overall", "")

    if "🟢" in overall and week_chg >= 3:
        report += "### 強勢多頭情境\n"
        report += "- 🔥 綜合訊號偏多但週漲幅已達 3%+，短線過熱\n"
        report += "- 持有者續抱，但不宜追高加碼\n"
        report += f"- 等待回調至 {price_now * 0.97:.2f} ~ {price_now * 0.98:.2f} 再考慮加倉\n"
    elif "🟢" in overall and week_chg < 3:
        report += "### 偏多情境\n"
        report += "- ✅ 綜合訊號偏多，可維持現有倉位\n"
        report += "- 若出現 1-2 日回調（1-2%），可考慮小量加碼\n"
        report += f"- 目標進場區間：{price_now * 0.97:.2f} ~ {price_now * 0.98:.2f}\n"
    elif "🔴" in overall:
        report += "### 偏空情境\n"
        report += "- ⚠️ 綜合訊號偏空，建議觀望或降低倉位\n"
        report += "- 等待三大指標中至少兩個轉正向再進場\n"
        report += "- 若持有，考慮在反彈時減碼\n"
    else:
        report += "### 中性情境\n"
        report += "- 🟡 訊號中性，適合觀望\n"
        report += "- 可用定期定額小量參與，不建議大筆進場\n"
        report += "- 重點觀察：10Y 是否站穩 4.5% 以下、Big Tech 財報指引\n"

    # 關鍵價位
    report += f"""
### 關鍵價位

| 價位 | 意義 |
|------|------|
| {price_now * 0.95:.2f} | 短線支撐（-5%） |
| {price_now:.2f} | 當前價格 |
| {etf_latest.get('ma20', 'N/A')} | 月線（20MA） |
| {etf_latest.get('52w_high', 'N/A')} | 52 週高點 |

---

> ⚠️ 本報告為自動生成，僅供參考，不構成投資建議。
> 產生時間：{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
"""
    return report


def main():
    data = load_week_data(7)
    if not data:
        print("[ERROR] 無可用數據", file=sys.stderr)
        return

    report = generate_weekly(data)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_file = REPORT_DIR / f"weekly_{date_str}.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 週報已產生：{output_file}")


if __name__ == "__main__":
    main()
