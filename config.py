#!/usr/bin/env python3
"""
009805 監控系統 — 設定模組
從 config.yaml 載入所有設定，供各腳本使用
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"

_config_cache = None


def get_config() -> dict:
    """載入 config.yaml（帶快取），回傳完整設定 dict"""
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache
