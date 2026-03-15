#!/usr/bin/env python3
"""
Macro Validator Agent — 宏觀資料品質驗證
=========================================
驗證 Data Agent 抓取的資料品質：範圍檢查、異常跳動、
資料過期、日期對齊、最低歷史長度。

標準介面：run(data) → {status, duration_ms, checks_passed, checks_total, warnings}
"""

import time
from datetime import datetime, timedelta


VALIDATION_RULES = {
    'vix':   {'min': 5, 'max': 100, 'max_daily_pct': 50, 'label': 'VIX'},
    'dxy':   {'min': 80, 'max': 130, 'max_daily_pct': 5, 'label': 'DXY 美元指數'},
    'oil':   {'min': 10, 'max': 200, 'max_daily_pct': 15, 'label': 'WTI 原油'},
    'gold':  {'min': 1000, 'max': 10000, 'max_daily_pct': 10, 'label': '黃金'},
    'us10y': {'min': 0, 'max': 15, 'max_daily_pct': 20, 'label': 'US 10Y 殖利率'},
    'spy':   {'min': 100, 'max': 1500, 'max_daily_pct': 15, 'label': 'SPY'},
    'jpy':   {'min': 80, 'max': 250, 'max_daily_pct': 5, 'label': 'USD/JPY'},
    'hyg':   {'min': 50, 'max': 120, 'max_daily_pct': 10, 'label': 'HYG 高收益債'},
    'tlt':   {'min': 50, 'max': 200, 'max_daily_pct': 10, 'label': 'TLT 長期公債'},
}

MIN_HISTORY_DAYS = 15  # 計算 20 日斜率至少需要的天數
STALENESS_THRESHOLD_DAYS = 4  # 超過 N 天沒更新視為 stale


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] [Validator] {msg}")


def check_completeness(history):
    """檢查每個 symbol 是否有資料"""
    warnings = []
    expected = list(VALIDATION_RULES.keys()) + ['fear_greed']
    for key in expected:
        data = history.get(key, [])
        if not data:
            warnings.append({
                'level': 'ERROR', 'symbol': key,
                'msg': f'{key} 完全無資料，該指標不可信',
            })
    return warnings


def check_value_ranges(history):
    """檢查最新值是否在合理範圍"""
    warnings = []
    for key, rules in VALIDATION_RULES.items():
        data = history.get(key, [])
        if not data:
            continue
        latest = data[-1]['close']
        if latest < rules['min'] or latest > rules['max']:
            warnings.append({
                'level': 'ERROR', 'symbol': key,
                'msg': f'{rules["label"]} 最新值 {latest} 超出合理範圍 [{rules["min"]}, {rules["max"]}]',
            })
    return warnings


def check_daily_spikes(history):
    """檢查最新一天的日變化是否異常"""
    warnings = []
    for key, rules in VALIDATION_RULES.items():
        data = history.get(key, [])
        if len(data) < 2:
            continue
        latest = data[-1]['close']
        prev = data[-2]['close']
        if prev == 0:
            continue
        pct_chg = abs(latest - prev) / prev * 100
        if pct_chg > rules['max_daily_pct']:
            warnings.append({
                'level': 'WARN', 'symbol': key,
                'msg': f'{rules["label"]} 日變化 {pct_chg:.1f}% 超過閾值 {rules["max_daily_pct"]}%'
                       f' ({prev} → {latest})',
            })
    return warnings


def check_staleness(history):
    """檢查資料是否過期"""
    warnings = []
    today = datetime.now().date()
    for key in list(VALIDATION_RULES.keys()) + ['fear_greed']:
        data = history.get(key, [])
        if not data:
            continue
        last_date = datetime.strptime(data[-1]['date'], '%Y-%m-%d').date()
        gap = (today - last_date).days
        if gap > STALENESS_THRESHOLD_DAYS:
            warnings.append({
                'level': 'WARN', 'symbol': key,
                'msg': f'{key} 最後更新 {data[-1]["date"]}，已 {gap} 天未更新',
            })
    return warnings


def check_date_alignment(history):
    """檢查跨標的最新日期是否對齊"""
    warnings = []
    latest_dates = {}
    for key in VALIDATION_RULES.keys():
        data = history.get(key, [])
        if data:
            latest_dates[key] = data[-1]['date']

    if len(latest_dates) < 2:
        return warnings

    dates = list(latest_dates.values())
    max_date = max(dates)
    min_date = min(dates)
    max_dt = datetime.strptime(max_date, '%Y-%m-%d')
    min_dt = datetime.strptime(min_date, '%Y-%m-%d')
    gap = (max_dt - min_dt).days

    if gap > 2:
        lagging = [k for k, d in latest_dates.items() if d == min_date]
        warnings.append({
            'level': 'WARN', 'symbol': ','.join(lagging),
            'msg': f'日期不對齊：最新 {max_date} vs 最舊 {min_date}（差 {gap} 天），'
                   f'落後標的：{", ".join(lagging)}',
        })
    return warnings


def check_minimum_history(history):
    """檢查計算斜率所需的最低歷史長度"""
    warnings = []
    for key in list(VALIDATION_RULES.keys()) + ['fear_greed']:
        data = history.get(key, [])
        if 0 < len(data) < MIN_HISTORY_DAYS:
            warnings.append({
                'level': 'INFO', 'symbol': key,
                'msg': f'{key} 歷史僅 {len(data)} 天（建議 >= {MIN_HISTORY_DAYS} 天），斜率計算可能不準確',
            })
    return warnings


def check_0050_data(data):
    """檢查 0050 相關資料"""
    warnings = []
    rankings = data.get('rankings', [])
    holdings = data.get('holdings_0050', [])

    if not rankings:
        warnings.append({
            'level': 'ERROR', 'symbol': '0050',
            'msg': 'TAIFEX 市值排名無資料，0050 策略無法計算',
        })
    if not holdings:
        warnings.append({
            'level': 'WARN', 'symbol': '0050',
            'msg': '0050 持股名單無資料，納入/剔除分析不可靠',
        })
    return warnings


# ── Main Entry ──

def run(data: dict) -> dict:
    """執行所有驗證檢查"""
    start = time.time()

    history = data.get('indices_history', {})
    all_warnings = []
    checks_passed = 0
    checks_total = 0

    checks = [
        ('completeness', lambda: check_completeness(history)),
        ('value_ranges', lambda: check_value_ranges(history)),
        ('daily_spikes', lambda: check_daily_spikes(history)),
        ('staleness', lambda: check_staleness(history)),
        ('date_alignment', lambda: check_date_alignment(history)),
        ('minimum_history', lambda: check_minimum_history(history)),
        ('0050_data', lambda: check_0050_data(data)),
    ]

    for check_name, check_fn in checks:
        checks_total += 1
        try:
            warnings = check_fn()
            if not warnings:
                checks_passed += 1
                log(f"  {check_name}: PASS")
            else:
                has_error = any(w['level'] == 'ERROR' for w in warnings)
                icon = 'FAIL' if has_error else 'WARN'
                log(f"  {check_name}: {icon} ({len(warnings)} issues)")
                all_warnings.extend(warnings)
        except Exception as e:
            log(f"  {check_name}: ERROR ({e})")
            all_warnings.append({
                'level': 'ERROR', 'symbol': 'validator',
                'msg': f'{check_name} 檢查異常: {e}',
            })

    duration = int((time.time() - start) * 1000)

    has_errors = any(w['level'] == 'ERROR' for w in all_warnings)
    has_warns = any(w['level'] in ('WARN', 'INFO') for w in all_warnings)
    status = 'ERROR' if has_errors else 'WARN' if has_warns else 'OK'

    log(f"Done in {duration}ms — {checks_passed}/{checks_total} passed, "
        f"{len(all_warnings)} warnings, status={status}")

    return {
        'status': status,
        'duration_ms': duration,
        'checks_passed': checks_passed,
        'checks_total': checks_total,
        'warnings': all_warnings,
    }


if __name__ == "__main__":
    import json
    # Quick test with existing data
    data_path = Path(__file__).parent.parent.parent / "data"
    hist_path = data_path / "indices_history.json"
    if hist_path.exists():
        with open(hist_path, 'r') as f:
            history = json.load(f)
        result = run({'indices_history': history, 'rankings': [], 'holdings_0050': []})
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("No indices_history.json found")
