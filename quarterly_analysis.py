#!/usr/bin/env python3
"""
009805 ETF 每季分析策略報告
讀取過去一季（~60-90 天）的歷史數據 → 季趨勢分析 → 策略框架
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

from config import get_config
from shared import DATA_DIR, REPORT_DIR, format_change, safe_json_load

config = get_config()


def load_quarter_data() -> list[Path]:
    """載入過去一季（90天）的數據"""
    files = sorted(DATA_DIR.glob("20*.json"))
    if not files:
        print("[ERROR] 無可用數據", file=sys.stderr)
        return []
    return files[-90:]  # 最多 90 天


def generate_quarterly(data_files: list[Path]) -> str:
    """生成每季分析報告"""
    if not data_files:
        return "# 無可用數據"

    # 載入所有數據
    all_data = []
    for f in data_files:
        d = safe_json_load(f)
        if d is not None:
            all_data.append(d)

    if not all_data:
        return "# 數據載入失敗"

    latest = all_data[-1]
    first = all_data[0]

    date_end = latest.get("date", "N/A")
    date_start = first.get("date", "N/A")

    # ---- ETF 季表現 ----
    etf_latest = latest.get("etf", {})
    etf_first = first.get("etf", {})
    price_end = etf_latest.get("price") or 0
    price_start = etf_first.get("price") or 0
    q_chg = ((price_end - price_start) / price_start * 100) if price_start else 0

    # 季高低點
    all_prices = []
    monthly_prices = defaultdict(list)
    for d in all_data:
        etf = d.get("etf", {})
        p = etf.get("price")
        if p:
            all_prices.append(p)
            month = d.get("date", "")[:7]
            monthly_prices[month].append(p)

    q_high = max(all_prices) if all_prices else 0
    q_low = min(all_prices) if all_prices else 0

    # ---- 月均價 ----
    monthly_avg = {}
    for month, prices in sorted(monthly_prices.items()):
        monthly_avg[month] = sum(prices) / len(prices)

    # ---- 10Y 季變化 ----
    tnx_latest = latest.get("indicators", {}).get("treasury_10y", {})
    tnx_first = first.get("indicators", {}).get("treasury_10y", {})
    tnx_end = tnx_latest.get("current", 0) or 0
    tnx_start = tnx_first.get("current", 0) or 0

    # 收集所有殖利率
    all_tnx = []
    for d in all_data:
        t = d.get("indicators", {}).get("treasury_10y", {}).get("current")
        if t:
            all_tnx.append(t)

    # ---- 匯率季變化 ----
    fx_latest = latest.get("indicators", {}).get("forex", {})
    fx_first = first.get("indicators", {}).get("forex", {})
    fx_end = fx_latest.get("current", 0) or 0
    fx_start = fx_first.get("current", 0) or 0

    # ---- 波動率與 Sharpe 近似 ----
    if len(all_prices) >= 10:
        daily_returns = []
        for i in range(1, len(all_prices)):
            r = (all_prices[i] - all_prices[i-1]) / all_prices[i-1]
            daily_returns.append(r)
        avg_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = variance ** 0.5
        annual_vol = std_dev * (252 ** 0.5) * 100
        sharpe_approx = (avg_return * 252) / (std_dev * (252 ** 0.5)) if std_dev > 0 else 0
    else:
        annual_vol = 0
        sharpe_approx = 0

    # ---- 生成報告 ----
    report = f"""# 📊 009805 每季分析策略報告

> **區間：{date_start} → {date_end}**｜數據天數：{len(all_data)} 天

---

## 📈 季度績效摘要

| 指標 | 數值 |
|------|------|
| 季初價格 | {price_start} |
| 季末價格 | **{price_end}** |
| 季漲跌 | **{q_chg:+.2f}%** |
| 季最高 | {q_high:.2f} |
| 季最低 | {q_low:.2f} |
| 季振幅 | {((q_high - q_low) / q_low * 100) if q_low else 0:.1f}% |
| 年化波動率 | {annual_vol:.1f}% |
| Sharpe (近似) | {sharpe_approx:.2f} |

---

## 📅 月均價格走勢

| 月份 | 月均價 | 月變動 |
|------|--------|--------|
"""
    prev_avg = None
    for month, avg in sorted(monthly_avg.items()):
        chg = ""
        if prev_avg:
            m_chg = (avg - prev_avg) / prev_avg * 100
            chg = format_change(m_chg)
        report += f"| {month} | {avg:.2f} | {chg} |\n"
        prev_avg = avg

    # ---- 三大指標季分析 ----
    report += "\n---\n\n## 🔭 三大指標季度分析\n\n"

    # 10Y
    tnx_chg = tnx_end - tnx_start if tnx_end and tnx_start else 0
    tnx_high = max(all_tnx) if all_tnx else 0
    tnx_low = min(all_tnx) if all_tnx else 0
    tnx_bp = tnx_chg * 100  # convert to basis points
    tnx_q_threshold = config.get("treasury", {}).get("alert_change_1w", 0.10) * 2  # quarterly: ~2x weekly

    report += f"""### ① 美國 10Y 公債殖利率

| 指標 | 數值 |
|------|------|
| 季初 | {tnx_start:.2f}% |
| 季末 | **{tnx_end:.2f}%** |
| 季變動 | {tnx_bp:+.0f} bp |
| 季最高 | {tnx_high:.2f}% |
| 季最低 | {tnx_low:.2f}% |

"""
    if tnx_chg < -tnx_q_threshold:
        report += f"> 🟢 季度殖利率下行 >{tnx_q_threshold*100:.0f}bp，對公用事業顯著利多\n\n"
    elif tnx_chg > tnx_q_threshold:
        report += f"> 🔴 季度殖利率上行 >{tnx_q_threshold*100:.0f}bp，公用事業估值承壓\n\n"
    else:
        report += "> 🟡 殖利率區間震盪，對 ETF 影響中性\n\n"

    # Big Tech
    bt_latest = latest.get("indicators", {}).get("big_tech", {})
    report += f"""### ② Big Tech Capex 代理

| 股票 | 股價 | 月變化 |
|------|------|--------|
"""
    if bt_latest:
        for sym, info in bt_latest.get("stocks", {}).items():
            chg = info.get("changes", {}).get("1m", "N/A")
            report += f"| {sym} | ${info.get('price', 'N/A')} | {format_change(chg)} |\n"

    report += f"""
> 關鍵問題：大型科技公司是否維持/上調 AI capex 指引？
> 下次確認時機：Q2 財報季（7 月下旬）

"""

    # 匯率
    fx_chg = fx_end - fx_start if fx_end and fx_start else 0
    fx_jiao = fx_chg * 10  # convert TWD to 角
    fx_q_threshold = config.get("forex", {}).get("alert_change_1w", 0.30) * 3  # quarterly: ~3x weekly

    report += f"""### ③ USD/TWD 匯率

| 指標 | 數值 |
|------|------|
| 季初 | {fx_start:.2f} |
| 季末 | **{fx_end:.2f}** |
| 季變動 | {fx_jiao:+.0f} 角 |

"""
    if fx_chg < -fx_q_threshold:
        report += f"> 🔴 台幣升值 >{fx_q_threshold*10:.0f} 角，匯損顯著\n\n"
    elif fx_chg > fx_q_threshold:
        report += f"> 🟢 台幣貶值 >{fx_q_threshold*10:.0f} 角，匯兌收益\n\n"
    else:
        report += "> 🟡 匯率波動可控\n\n"

    # ---- 策略框架：情境分析（條件真正影響輸出） ----
    report += """---
## 🎯 季度策略框架

### 情境分析

| 情境 | 條件 | 策略 |
|------|------|------|
"""

    # 順風 / 逆風 / 震盪 — 單一 if/elif/else，只輸出一列
    if tnx_chg < -tnx_q_threshold and q_chg > 0:
        report += "| 🟢 **順風** | 殖利率下行 + 價格上行 | 持續布局，拉回加碼 |\n"
    elif tnx_chg > tnx_q_threshold and q_chg < 0:
        report += "| 🔴 **逆風** | 殖利率上行 + 價格下行 | 降低部位，等待轉折 |\n"
    else:
        report += "| 🟡 **震盪** | 指標分歧、無明確方向 | 定期定額，不追高不殺低 |\n"

    report += """\n\n### 下季關鍵事件\n\n| 時間 | 事件 | 影響 |\n|------|------|------|\n"""

    # 從 config 載入事件日曆
    events_cfg = config.get("events", [])
    now = datetime.now(timezone.utc)

    if events_cfg:
        for evt in events_cfg:
            try:
                evt_date = datetime.strptime(evt["date"], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                report += f"| {evt_date.strftime('%m/%d')} | {evt['name']} | {evt.get('impact', '')} |\n"
            except (ValueError, KeyError):
                continue
    else:
        # fallback: 從目前日期往後推一季
        fallback_events = [
            (now + timedelta(days=22), "FOMC 6月", "利率預期"),
            (now + timedelta(days=55), "Q2 財報季開始", "AI capex 指引（最關鍵）"),
            (now + timedelta(days=60), "FOMC 7月", "利率預期"),
            (now + timedelta(days=115), "FOMC 9月", "利率預期"),
        ]
        for dt, name, impact in fallback_events:
            report += f"| {dt.strftime('%m/%d')} | {name} | {impact} |\n"

    report += f"""
### 倉位建議（參考）

```
本季區間預估：{q_low:.1f} ~ {q_high:.1f}（基於歷史振幅）

保守型：{q_low * 1.05:.1f} 以下分批布局，倉位上限 30%
穩健型：{q_low * 1.05:.1f} ~ {price_end * 0.95:.1f} 分批 + 定期定額，倉位 20-50%
積極型：現價附近建立 20% + 每跌 5% 加碼 10%，倉位上限 60%
```

---

> ⚠️ 本報告為自動生成，僅供參考，不構成投資建議。
> 產生時間：{now.strftime('%Y-%m-%dT%H:%M:%SZ')}
"""
    return report


def main():
    data_files = load_quarter_data()
    if not data_files:
        print("[ERROR] 無可用數據", file=sys.stderr)
        return

    report = generate_quarterly(data_files)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_file = REPORT_DIR / f"quarterly_{date_str}.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 季報已產生：{output_file}")


if __name__ == "__main__":
    main()
