#!/usr/bin/env python3
"""
Wolf Pack Agent 共用設定
========================
自動偵測 Mac / Windows / GitHub Actions 環境，統一路徑管理。
"""

import os
import platform
from pathlib import Path

# ── 環境偵測 ──
IS_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

# ── 路徑設定 ──
if IS_GITHUB:
    FINANCE_DATA = Path(os.environ.get("GITHUB_WORKSPACE", "."))
elif IS_MAC:
    FINANCE_DATA = Path.home() / "FinanceData"
elif IS_WINDOWS:
    # Google Drive 同步路徑
    _gdrive = Path("G:/其他電腦/我的 Mac/FinanceData")
    if _gdrive.exists():
        FINANCE_DATA = _gdrive
    else:
        FINANCE_DATA = Path.home() / "FinanceData"
else:
    FINANCE_DATA = Path.home() / "FinanceData"

ETF_BASE = FINANCE_DATA / "history" / "ETF"
REPO_DIR = Path(__file__).resolve().parent.parent.parent  # wolf-pack-dashboard/
SCRIPTS_DIR = REPO_DIR / "scripts"
AGENTS_DIR = SCRIPTS_DIR / "agents"
DATA_DIR = REPO_DIR / "data"
LOG_DIR = REPO_DIR / "logs" if IS_GITHUB else FINANCE_DATA / "logs"
REPORT_DIR = REPO_DIR if IS_GITHUB else FINANCE_DATA  # signal reports go here

# ── ETF 設定 ──
ETF_IDS = ["00981A", "00980A", "00982A", "00991A", "00993A"]
PRIMARY_ETF = "00981A"

# ── 通知設定 ──
LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN", "")

# ── 確保目錄存在 ──
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_env_info() -> str:
    env = "GitHub Actions" if IS_GITHUB else "Mac" if IS_MAC else "Windows" if IS_WINDOWS else "Unknown"
    return f"環境={env}, 資料={FINANCE_DATA}, Repo={REPO_DIR}"
