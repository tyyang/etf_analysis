# AGENTS.md

## Project

Python 3.12 CLI pipeline that fetches ETF and economic indicator data from Yahoo Finance and generates daily/weekly/quarterly Markdown reports for Taiwan-listed ETF 009805 (新光美國電力基建).

## Dependencies

```bash
pip install pyyaml
```

No `requirements.txt`, no build system, no package manager manifest.

## Running

Scripts resolve paths via `shared.ROOT` (`Path(__file__).resolve().parent`), so they can be run from any working directory.

| Command | Effect |
|---------|--------|
| `python run_all.py` | Fetch + daily report (default) |
| `python run_all.py --fetch` | Fetch only |
| `python run_all.py --report` | Daily report only (uses existing data) |
| `python run_all.py --weekly` | Fetch + daily + weekly report |
| `python run_all.py --quarterly` | Fetch + daily + quarterly report |
| `python run_all.py --all` | All steps |

Individual scripts can also be run standalone: `fetch_indicators.py`, `daily_report.py`, `weekly_analysis.py`, `quarterly_analysis.py`.

## Testing

```bash
python -m unittest discover -s tests -v
```

41 tests covering `shared.py`, `fetch_indicators.py` utils, and report generators.

## Architecture

- `config.py` – YAML config loader with cache (`get_config()`)
- `shared.py` – Path constants, `safe_json_load()`, `format_change()`, `yahoo_chart()` API wrapper with rate limiting + exponential backoff
- `config.yaml` – Thresholds, holdings, position strategy, event calendar, report settings
- `fetch_indicators.py` → `data/YYYY-MM-DD.json` + deduplicated append to `data/history.jsonl`
- `daily_report.py`, `weekly_analysis.py`, `quarterly_analysis.py` → `reports/*.md`

Data flow: `config.yaml` + Yahoo Finance → `fetch_indicators.py` → `data/` → report scripts → `reports/`

## Gotchas

- **No CI, no linting.**
- Yahoo Finance chart API is unauthenticated (no API key needed).
- `yahoo_chart()` has built-in rate limiting (1.5s sleep per call) and exponential backoff on retries — a full fetch cycle takes ~30s+.
- Weekly/quarterly reports need multi-day history to be meaningful; insufficient data produces trivial output.
- `data/` and `reports/` are gitignored (generated at runtime).
