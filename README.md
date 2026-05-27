# 009805 ETF 監控系統

自動化監控 **009805 新光美國電力基建 ETF** 的三大核心指標，每日抓取 Yahoo Finance 數據並生成日報/週報/季報 Markdown 報告。

## 追蹤指標

| 指標 | 權重 | 影響邏輯 |
|------|------|----------|
| 美國 10Y 公債殖利率 (^TNX) | 35% | 殖利率↑ → 公用事業估值↓ |
| 大型科技股 Capex 代理 (GOOGL/META/MSFT/AMZN) | 45% | AI capex 為核心驅動力 |
| USD/TWD 匯率 (USDTWD=X) | 20% | 台幣貶值 → ETF 台幣計價有利 |

另外追蹤 ETF 前十大持股個股表現、技術指標、倉位策略。

## 快速開始

```bash
# 安裝依賴
pip install pyyaml

# 一鍵執行：抓取數據 + 產生每日報告
python run_all.py

# 產生全部報告（抓取 + 日報 + 週報 + 季報）
python run_all.py --all
```

## 使用說明

| 命令 | 效果 |
|------|------|
| `python run_all.py` | 抓取數據 + 日報（預設） |
| `python run_all.py --fetch` | 僅抓取數據 |
| `python run_all.py --report` | 僅產生日報（使用既有數據） |
| `python run_all.py --weekly` | 抓取 + 日報 + 週報 |
| `python run_all.py --quarterly` | 抓取 + 日報 + 季報 |
| `python run_all.py --all` | 全部步驟 |

也可單獨執行各腳本：
- `fetch_indicators.py` — 抓取所有指標
- `daily_report.py` — 每日報告
- `weekly_analysis.py` — 每週策略報告
- `quarterly_analysis.py` — 每季策略框架

## 設定檔

`config.yaml` 包含所有可調整參數：
- 指標閾值與權重
- ETF 前十大持股清單
- 技術面參數（RSI、均線）
- 倉位策略區間
- 關鍵事件日曆

修改後立即生效，無需重啟。

## 測試

```bash
python -m unittest discover -s tests -v
```

41 個測試覆蓋共用工具、數據抓取邏輯與報告生成。

## 資料流

```
config.yaml ──┐
              ├──> fetch_indicators.py ──> data/YYYY-MM-DD.json
              │                         ──> data/history.jsonl
Yahoo Finance ┘
                              │
                              ▼
                    daily_report.py      ──> reports/daily_*.md
                    weekly_analysis.py   ──> reports/weekly_*.md
                    quarterly_analysis.py ──> reports/quarterly_*.md
```

## 專案結構

```
.
├── config.yaml              # 設定檔
├── config.py                # 設定載入模組
├── shared.py                # 共用工具（API 封裝、格式化）
├── fetch_indicators.py      # 數據抓取
├── daily_report.py          # 每日報告生成
├── weekly_analysis.py       # 每週分析報告生成
├── quarterly_analysis.py    # 每季策略報告生成
├── run_all.py               # 一鍵執行入口
├── tests/                   # 單元測試
├── data/                    # 數據輸出（gitignore）
└── reports/                 # 報告輸出（gitignore）
```

## 注意事項

- 使用 Yahoo Finance 公開 API，無需 API Key
- 內建速率限制（每次呼叫間隔 1.5 秒）與指數退避重試
- 完整抓取週期約需 30 秒以上
- 週報/季報需要多日歷史數據才有分析價值

## 免責聲明

本系統為自動化工具，輸出僅供參考，不構成投資建議。投資決策請自行判斷。
