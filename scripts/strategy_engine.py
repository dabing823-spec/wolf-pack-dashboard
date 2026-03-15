#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wolf Pack Strategy Engine — 策略指標計算引擎
=============================================
讀取 dashboard.json + etf_pages.json，計算進階策略指標，
輸出 strategy.json 供前端使用。

用法:
  python strategy_engine.py

輸出:
  ../data/strategy.json

計算內容:
  A. Signal Backtest (信號回測績效)
  B. Manager Style Analysis (經理人風格分析)
  C. Consensus Trend (共識強度趨勢)
  D. Velocity Indicator (異動速度指標)
  E. Action Recommendation (操作建議)
  F. Industry Exposure (產業曝險)
  H. Holdings Overlap Heatmap (持倉重疊)
  I. Market Timing Score (經理人擇時能力)
"""

import sys
import json
import os
import time
import platform
import io
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd

# ═══════════════════════════════════════
# 路徑設定（自動偵測 Mac / Windows / GitHub Actions）
# ═══════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
DATA_DIR = REPO_DIR / "data"

# Import config if available
try:
    sys.path.insert(0, str(SCRIPT_DIR))
    from agents.config import ETF_IDS, PRIMARY_ETF, DATA_DIR as CFG_DATA_DIR
    DATA_DIR = CFG_DATA_DIR
except ImportError:
    ETF_IDS = ["00981A", "00980A", "00982A", "00991A", "00993A"]
    PRIMARY_ETF = "00981A"

DASHBOARD_PATH = DATA_DIR / "dashboard.json"
ETF_PAGES_PATH = DATA_DIR / "etf_pages.json"
STRATEGY_PATH = DATA_DIR / "strategy.json"
PRICE_CACHE_PATH = DATA_DIR / "price_cache.json"

# HTTP headers for TWSE API
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ═══════════════════════════════════════
# 0050 / 市值權重 設定
# ═══════════════════════════════════════
TAIFEX_RANKING_URL = "https://www.taifex.com.tw/cht/9/futuresQADetail"
MONEYDJ_ETF_URL = "https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid={}.TW"
THRESHOLD_0050_IN = 40    # rank <= 40 且不在 0050 → 潛在納入
THRESHOLD_0050_OUT = 60   # rank > 60 且在 0050 → 潛在剔除

# ═══════════════════════════════════════
# 風險訊號設定
# ═══════════════════════════════════════
RISK_SYMBOLS = {
    'vix':   '%5EVIX',
    'dxy':   'DX-Y.NYB',
    'oil':   'CL%3DF',
    'gold':  'GC%3DF',
    'us10y': '%5ETNX',
    'spy':   'SPY',
    'jpy':   'JPY%3DX',
    'hyg':   'HYG',
    'tlt':   'TLT',
}
INDICES_HISTORY_PATH = DATA_DIR / "indices_history.json"

# ═══════════════════════════════════════
# 產業對照表（常見台股代碼 -> 產業）
# ═══════════════════════════════════════
INDUSTRY_MAP = {
    # 半導體
    '2330': '半導體', '2454': '半導體', '3711': '半導體', '2379': '半導體',
    '3034': '半導體', '2303': '半導體', '6770': '半導體', '3529': '半導體',
    '5274': '半導體', '6415': '半導體', '3443': '半導體', '2344': '半導體',
    '2449': '半導體', '6269': '半導體', '3661': '半導體', '2408': '半導體',
    '6488': '半導體', '6547': '半導體', '3105': '半導體', '2436': '半導體',
    '6806': '半導體', '5347': '半導體', '6533': '半導體', '4966': '半導體',
    '8150': '半導體', '5269': '半導體', '6278': '半導體', '6223': '半導體',
    '3707': '半導體', '2458': '半導體', '6239': '半導體',
    # 電子零組件
    '2317': '電子零組件', '2382': '電子零組件', '2327': '電子零組件',
    '3037': '電子零組件', '2345': '電子零組件', '3036': '電子零組件',
    '6285': '電子零組件', '2492': '電子零組件', '3044': '電子零組件',
    '3023': '電子零組件', '2059': '電子零組件', '6271': '電子零組件',
    # 光電 / 面板
    '3008': '光電', '2409': '光電', '3481': '光電', '6176': '光電',
    '2393': '光電', '6116': '光電', '6189': '光電',
    # 通訊網路
    '2412': '通訊網路', '3045': '通訊網路', '4904': '通訊網路',
    '6285': '通訊網路', '2332': '通訊網路',
    # 電腦及週邊
    '2357': '電腦及週邊', '2353': '電腦及週邊', '2356': '電腦及週邊',
    '2324': '電腦及週邊', '2365': '電腦及週邊', '2377': '電腦及週邊',
    '3231': '電腦及週邊', '3706': '電腦及週邊', '3013': '電腦及週邊',
    '2395': '電腦及週邊', '3005': '電腦及週邊',
    # 金融
    '2881': '金融', '2882': '金融', '2884': '金融', '2886': '金融',
    '2891': '金融', '2892': '金融', '5880': '金融', '2880': '金融',
    '2883': '金融', '2887': '金融', '2885': '金融', '2888': '金融',
    '2890': '金融',
    # 傳產 / 塑化
    '1301': '塑化', '1303': '塑化', '1326': '塑化', '6505': '塑化',
    # 鋼鐵
    '2002': '鋼鐵', '2014': '鋼鐵', '2027': '鋼鐵', '9958': '鋼鐵',
    # 紡織
    '1402': '紡織', '1477': '紡織', '9910': '紡織',
    # 食品
    '1216': '食品', '1227': '食品', '2912': '食品',
    # 航運
    '2603': '航運', '2609': '航運', '2615': '航運', '2618': '航運',
    # 營建
    '2501': '營建', '2504': '營建', '2520': '營建', '5522': '營建',
    # 汽車
    '2201': '汽車', '2207': '汽車',
    # 電機
    '1504': '電機', '1503': '電機', '6213': '電機', '1513': '電機',
    '8046': '電機', '3617': '電機',
    # 生技醫療
    '4743': '生技醫療', '6446': '生技醫療', '1760': '生技醫療',
    '4142': '生技醫療', '6472': '生技醫療', '4737': '生技醫療',
    # 軟體 / AI
    '6694': '軟體', '6612': '軟體', '3588': '軟體',
    # 電子通路
    '3702': '電子通路', '6112': '電子通路', '2347': '電子通路',
    # 其他電子
    '3665': '其他電子', '2301': '其他電子', '2308': '其他電子',
    '6669': '其他電子', '6515': '其他電子', '3380': '其他電子',
}


def load_json(path):
    """載入 JSON 檔案"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    """儲存 JSON 檔案"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def clean(obj):
    """清理特殊型別，確保 JSON 可序列化"""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean(v) for v in obj]
    elif isinstance(obj, float):
        if obj != obj:  # NaN
            return None
        return round(obj, 4)
    elif hasattr(obj, 'item'):
        return obj.item()
    elif hasattr(obj, 'isoformat'):
        return str(obj)
    return obj


# ═══════════════════════════════════════
# A. Signal Backtest (信號回測績效)
# ═══════════════════════════════════════

def fetch_stock_prices(stock_code, year, month):
    """從 TWSE 抓取個股月成交資訊，回傳 {date: close_price}"""
    import requests

    url = (f"https://www.twse.com.tw/exchangeReport/STOCK_DAY"
           f"?response=json&date={year}{month:02d}01&stockNo={stock_code}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        if data.get('stat') != 'OK' or not data.get('data'):
            return {}

        prices = {}
        for row in data['data']:
            # row[0] = '115/03/13' (ROC date), row[6] = closing price
            parts = row[0].strip().split('/')
            if len(parts) == 3:
                dt = f"{int(parts[0]) + 1911}-{parts[1]}-{parts[2]}"
                close_str = row[6].replace(',', '').strip()
                try:
                    prices[dt] = float(close_str)
                except ValueError:
                    pass
        return prices
    except Exception as e:
        print(f"    TWSE API error for {stock_code} ({year}/{month:02d}): {e}")
        return {}


def fetch_stock_price_range(stock_code, start_date, end_date, price_cache):
    """抓取一檔股票在日期範圍內的收盤價，使用快取"""
    if stock_code in price_cache:
        return price_cache[stock_code]

    all_prices = {}
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Iterate month by month
    current = start.replace(day=1)
    while current <= end:
        prices = fetch_stock_prices(stock_code, current.year, current.month)
        all_prices.update(prices)
        time.sleep(0.5)  # Rate limiting

        # Next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    price_cache[stock_code] = all_prices
    return all_prices


def calc_signal_backtest(dashboard):
    """A. 信號回測績效"""
    print("  [A] Signal Backtest (信號回測績效)...")
    signals = dashboard.get('laomo_signals', [])
    if not signals:
        print("      No signals found, skipping.")
        return {'summary': {}, 'by_type': {}, 'signals': []}

    # Load price cache
    price_cache = {}
    if PRICE_CACHE_PATH.exists():
        try:
            price_cache = load_json(PRICE_CACHE_PATH)
            print(f"      Loaded price cache: {len(price_cache)} stocks")
        except Exception:
            pass

    # Determine date range needed
    signal_dates = [s['date'] for s in signals]
    min_date = min(signal_dates)
    # Need prices up to 60 trading days after last signal
    max_signal_date = max(signal_dates)
    max_date_dt = datetime.strptime(max_signal_date, "%Y-%m-%d") + timedelta(days=90)
    max_date = max_date_dt.strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    if max_date > today:
        max_date = today

    # Unique stocks in signals
    stock_codes = list(set(s['code'] for s in signals))
    print(f"      {len(signals)} signals, {len(stock_codes)} unique stocks")
    print(f"      Date range: {min_date} ~ {max_date}")

    # Fetch prices for each stock
    fetched = 0
    for code in stock_codes:
        if code in price_cache and price_cache[code]:
            continue
        print(f"      Fetching prices for {code}...")
        try:
            prices = fetch_stock_price_range(code, min_date, max_date, price_cache)
            if prices:
                fetched += 1
        except Exception as e:
            print(f"      Failed to fetch {code}: {e}")

    if fetched > 0:
        print(f"      Fetched {fetched} new stocks, saving cache...")
        try:
            save_json(PRICE_CACHE_PATH, price_cache)
        except Exception as e:
            print(f"      Cache save failed: {e}")

    # Calculate returns for each signal
    result_signals = []
    for sig in signals:
        code = sig['code']
        sig_date = sig['date']
        prices = price_cache.get(code, {})
        if not prices:
            continue

        sorted_dates = sorted(prices.keys())
        # Find signal date index
        try:
            idx = next(i for i, d in enumerate(sorted_dates) if d >= sig_date)
        except StopIteration:
            continue

        entry_price = prices.get(sorted_dates[idx])
        if not entry_price or entry_price <= 0:
            continue

        def get_return_nd(n):
            target_idx = idx + n
            if target_idx < len(sorted_dates):
                p = prices.get(sorted_dates[target_idx])
                if p and p > 0:
                    return round((p - entry_price) / entry_price * 100, 2)
            return None

        r10 = get_return_nd(10)
        r20 = get_return_nd(20)
        r60 = get_return_nd(60)

        result_signals.append({
            'date': sig_date,
            'code': code,
            'name': sig.get('name', ''),
            'type': sig.get('type', ''),
            'weight_chg': sig.get('weight_chg', 0),
            'confidence': sig.get('confidence', ''),
            'return_10d': r10,
            'return_20d': r20,
            'return_60d': r60,
        })

    # Summary statistics
    r10_vals = [s['return_10d'] for s in result_signals if s['return_10d'] is not None]
    r20_vals = [s['return_20d'] for s in result_signals if s['return_20d'] is not None]

    summary = {
        'total_signals': len(signals),
        'evaluated_signals': len(result_signals),
        'win_rate_10d': round(sum(1 for v in r10_vals if v > 0) / max(len(r10_vals), 1) * 100, 1),
        'win_rate_20d': round(sum(1 for v in r20_vals if v > 0) / max(len(r20_vals), 1) * 100, 1),
        'avg_return_10d': round(sum(r10_vals) / max(len(r10_vals), 1), 2),
        'avg_return_20d': round(sum(r20_vals) / max(len(r20_vals), 1), 2),
    }

    # By type
    by_type = {}
    for sig_type in set(s['type'] for s in result_signals):
        typed = [s for s in result_signals if s['type'] == sig_type]
        t10 = [s['return_10d'] for s in typed if s['return_10d'] is not None]
        t20 = [s['return_20d'] for s in typed if s['return_20d'] is not None]
        by_type[sig_type] = {
            'count': len(typed),
            'win_rate_10d': round(sum(1 for v in t10 if v > 0) / max(len(t10), 1) * 100, 1),
            'avg_return_10d': round(sum(t10) / max(len(t10), 1), 2),
            'win_rate_20d': round(sum(1 for v in t20 if v > 0) / max(len(t20), 1) * 100, 1),
            'avg_return_20d': round(sum(t20) / max(len(t20), 1), 2),
        }

    print(f"      Summary: {summary['evaluated_signals']} evaluated, "
          f"10d WR={summary['win_rate_10d']}%, 20d WR={summary['win_rate_20d']}%")

    return {
        'summary': summary,
        'by_type': by_type,
        'signals': result_signals,
    }


# ═══════════════════════════════════════
# B. Manager Style Analysis (經理人風格分析)
# ═══════════════════════════════════════

def calc_manager_styles(etf_pages):
    """B. 經理人風格分析"""
    print("  [B] Manager Style Analysis (經理人風格分析)...")
    styles = {}

    for etf_id in ETF_IDS:
        page = etf_pages.get(etf_id)
        if not page or not page.get('date_records'):
            continue

        records = page['date_records']
        n_records = len(records)
        if n_records < 2:
            continue

        # Turnover rate: % of stocks that change each day
        turnover_rates = []
        for i in range(1, n_records):
            curr_codes = set(h['code'] for h in records[i].get('holdings', []))
            prev_codes = set(h['code'] for h in records[i - 1].get('holdings', []))
            union = curr_codes | prev_codes
            if len(union) == 0:
                continue
            changed = len(curr_codes.symmetric_difference(prev_codes))
            turnover_rates.append(changed / len(union) * 100)

        avg_turnover = round(sum(turnover_rates) / max(len(turnover_rates), 1), 2)

        # Average Top5 concentration
        concentrations = []
        n_stocks_list = []
        for rec in records:
            holdings = rec.get('holdings', [])
            sorted_h = sorted(holdings, key=lambda h: h.get('weight', 0), reverse=True)
            top5_weight = sum(h.get('weight', 0) for h in sorted_h[:5])
            concentrations.append(top5_weight)
            n_stocks_list.append(len(holdings))

        avg_concentration = round(sum(concentrations) / max(len(concentrations), 1), 2)
        avg_n_stocks = round(sum(n_stocks_list) / max(len(n_stocks_list), 1), 1)

        # Change frequency: days with >0.3% weight change on any stock / total days
        change_days = 0
        for i in range(1, n_records):
            curr_map = {h['code']: h.get('weight', 0) for h in records[i].get('holdings', [])}
            prev_map = {h['code']: h.get('weight', 0) for h in records[i - 1].get('holdings', [])}
            significant = False
            all_codes = set(curr_map.keys()) | set(prev_map.keys())
            for code in all_codes:
                chg = abs(curr_map.get(code, 0) - prev_map.get(code, 0))
                if chg > 0.3:
                    significant = True
                    break
            if significant:
                change_days += 1

        change_frequency = round(change_days / max(n_records - 1, 1) * 100, 1)

        # Style label
        if avg_turnover > 10:
            style_label = "積極操作"
        elif avg_turnover > 5:
            style_label = "穩健配置"
        else:
            style_label = "長期持有"

        styles[etf_id] = {
            'turnover_rate': avg_turnover,
            'avg_concentration': avg_concentration,
            'avg_n_stocks': avg_n_stocks,
            'change_frequency': change_frequency,
            'style_label': style_label,
            'n_records': n_records,
        }
        print(f"      {etf_id}: turnover={avg_turnover}%, style={style_label}")

    return styles


# ═══════════════════════════════════════
# C. Consensus Trend (共識強度趨勢)
# ═══════════════════════════════════════

def calc_consensus_trends(dashboard, etf_pages):
    """C. 共識強度趨勢 - 過去30天各股被多少ETF持有的變化"""
    print("  [C] Consensus Trend (共識強度趨勢)...")

    # Current consensus stocks (held by >=2 ETFs)
    consensus = dashboard.get('consensus', [])
    if not consensus:
        print("      No consensus stocks found.")
        return []

    # Get all available dates across ETFs (last 30)
    all_dates = set()
    for etf_id in ETF_IDS:
        page = etf_pages.get(etf_id)
        if page and page.get('dates'):
            all_dates.update(page['dates'])
    all_dates = sorted(all_dates)
    recent_dates = all_dates[-30:] if len(all_dates) >= 30 else all_dates

    # For each consensus stock, count ETFs holding it on each date
    trends = []
    for stock in consensus:
        code = stock['code']
        name = stock['name']
        trend = []

        for dt in recent_dates:
            n_etfs = 0
            for etf_id in ETF_IDS:
                page = etf_pages.get(etf_id)
                if not page or not page.get('date_records'):
                    continue
                # Find record for this date (or closest before)
                for rec in reversed(page['date_records']):
                    if rec['date'] <= dt:
                        codes_held = set(h['code'] for h in rec.get('holdings', []))
                        if code in codes_held:
                            n_etfs += 1
                        break
            trend.append({'date': dt, 'n_etfs': n_etfs})

        current_n = trend[-1]['n_etfs'] if trend else 0

        # Direction: compare first half vs second half average
        if len(trend) >= 6:
            first_half = sum(t['n_etfs'] for t in trend[:len(trend) // 2]) / (len(trend) // 2)
            second_half = sum(t['n_etfs'] for t in trend[len(trend) // 2:]) / (len(trend) - len(trend) // 2)
            if second_half > first_half + 0.3:
                direction = "rising"
            elif second_half < first_half - 0.3:
                direction = "falling"
            else:
                direction = "stable"
        else:
            direction = "stable"

        trends.append({
            'code': code,
            'name': name,
            'trend': trend,
            'current_n': current_n,
            'direction': direction,
        })

    # Sort by current_n descending, take top 15
    trends.sort(key=lambda t: t['current_n'], reverse=True)
    trends = trends[:15]
    print(f"      {len(trends)} consensus stocks tracked")
    return trends


# ═══════════════════════════════════════
# D. Velocity Indicator (異動速度指標)
# ═══════════════════════════════════════

def calc_velocity(dashboard):
    """D. 異動速度指標 - 00981A top20 股票的權重變化速度"""
    print("  [D] Velocity Indicator (異動速度指標)...")

    top20 = dashboard.get('top20_stocks', [])
    weight_history = dashboard.get('weight_history', {})

    if not top20 or not weight_history:
        print("      No data available.")
        return []

    velocity_list = []
    for stock in top20:
        code = stock['code']
        name = stock['name']
        current_weight = stock.get('weight', 0)

        hist = weight_history.get(code, [])
        if len(hist) < 2:
            continue

        weights = [h.get('weight', 0) for h in hist]

        # velocity_5d: average daily weight change over last 5 days
        if len(weights) >= 6:
            changes_5d = [weights[i] - weights[i - 1] for i in range(len(weights) - 5, len(weights))]
            velocity_5d = round(sum(changes_5d) / len(changes_5d), 4)
        elif len(weights) >= 2:
            changes = [weights[i] - weights[i - 1] for i in range(1, len(weights))]
            velocity_5d = round(sum(changes[-5:]) / len(changes[-5:]), 4)
        else:
            velocity_5d = 0

        # velocity_10d: average daily weight change over last 10 days
        if len(weights) >= 11:
            changes_10d = [weights[i] - weights[i - 1] for i in range(len(weights) - 10, len(weights))]
            velocity_10d = round(sum(changes_10d) / len(changes_10d), 4)
        elif len(weights) >= 2:
            changes = [weights[i] - weights[i - 1] for i in range(1, len(weights))]
            velocity_10d = round(sum(changes[-10:]) / len(changes[-10:]), 4)
        else:
            velocity_10d = 0

        acceleration = round(velocity_5d - velocity_10d, 4)

        # Signal classification
        if velocity_5d > 0.3:
            signal = "急買"
        elif velocity_5d < -0.3:
            signal = "急賣"
        elif 0.1 <= velocity_5d <= 0.3:
            signal = "慢加"
        elif -0.3 <= velocity_5d <= -0.1:
            signal = "慢減"
        else:
            signal = "持平"

        velocity_list.append({
            'code': code,
            'name': name,
            'weight': current_weight,
            'velocity_5d': velocity_5d,
            'velocity_10d': velocity_10d,
            'acceleration': acceleration,
            'signal': signal,
        })

    velocity_list.sort(key=lambda v: abs(v['velocity_5d']), reverse=True)
    print(f"      {len(velocity_list)} stocks analyzed")
    return velocity_list


# ═══════════════════════════════════════
# E. Action Recommendation (操作建議)
# ═══════════════════════════════════════

def calc_recommendations(dashboard, velocity_data):
    """E. 多因子操作建議"""
    print("  [E] Action Recommendation (操作建議)...")

    consensus = dashboard.get('consensus', [])
    conviction = dashboard.get('conviction', [])
    cash_mode = dashboard.get('cash_mode', {})

    # Build lookup maps
    consensus_map = {s['code']: s for s in consensus}
    conviction_map = {s['code']: s for s in conviction}
    velocity_map = {v['code']: v for v in velocity_data}

    # Determine cash mode factor
    mode_str = cash_mode.get('mode', '')
    if '積極進攻' in mode_str or '進攻' in mode_str:
        cash_factor = 1
    elif '防守' in mode_str:
        cash_factor = -1
    else:
        cash_factor = 0

    # Get all candidate stocks (from consensus + top20 + conviction)
    all_codes = set()
    for s in consensus:
        all_codes.add(s['code'])
    for s in dashboard.get('top20_stocks', []):
        all_codes.add(s['code'])
    for s in conviction:
        all_codes.add(s['code'])

    # Stock name map
    name_map = {}
    weight_map = {}
    for s in consensus:
        name_map[s['code']] = s['name']
    for s in dashboard.get('top20_stocks', []):
        name_map[s['code']] = s['name']
        weight_map[s['code']] = s.get('weight', 0)
    for s in conviction:
        name_map[s['code']] = s['name']
        if s['code'] not in weight_map:
            weight_map[s['code']] = s.get('weight', 0)

    recommendations = []
    for code in all_codes:
        # Factor 1: Consensus
        cons = consensus_map.get(code)
        if cons:
            n_etfs = cons.get('n_etfs', 0)
            if n_etfs >= 5:
                f_consensus = 5
            elif n_etfs >= 4:
                f_consensus = 3
            elif n_etfs >= 3:
                f_consensus = 2
            else:
                f_consensus = 0
        else:
            f_consensus = 0

        # Factor 2: Conviction (weight_chg over 20d)
        conv = conviction_map.get(code)
        if conv:
            wc = conv.get('weight_chg', 0)
            if wc > 1:
                f_conviction = 3
            elif wc > 0.5:
                f_conviction = 2
            elif wc > 0:
                f_conviction = 1
            elif wc < -0.5:
                f_conviction = -2
            else:
                f_conviction = 0
        else:
            f_conviction = 0

        # Factor 3: Velocity
        vel = velocity_map.get(code)
        if vel:
            sig = vel.get('signal', '持平')
            if sig == '急買':
                f_velocity = 2
            elif sig == '慢加':
                f_velocity = 1
            elif sig == '慢減':
                f_velocity = -1
            elif sig == '急賣':
                f_velocity = -2
            else:
                f_velocity = 0
        else:
            f_velocity = 0

        # Factor 4: Cash mode
        f_cash = cash_factor

        total_score = f_consensus + f_conviction + f_velocity + f_cash

        # Recommendation
        if total_score >= 6:
            rec = "強力買進"
        elif total_score >= 4:
            rec = "建議買進"
        elif total_score >= 2:
            rec = "觀望偏多"
        elif total_score >= 0:
            rec = "中性"
        else:
            rec = "建議觀望"

        recommendations.append({
            'code': code,
            'name': name_map.get(code, ''),
            'score': total_score,
            'factors': {
                'consensus': f_consensus,
                'conviction': f_conviction,
                'velocity': f_velocity,
                'cash_mode': f_cash,
            },
            'recommendation': rec,
            'current_weight': weight_map.get(code, 0),
        })

    recommendations.sort(key=lambda r: r['score'], reverse=True)
    recommendations = recommendations[:20]
    print(f"      Top recommendation: {recommendations[0]['name']}({recommendations[0]['code']}) "
          f"score={recommendations[0]['score']} -> {recommendations[0]['recommendation']}"
          if recommendations else "      No recommendations")
    return recommendations


# ═══════════════════════════════════════
# F. Industry Exposure (產業曝險)
# ═══════════════════════════════════════

def calc_industry_exposure(dashboard):
    """F. 產業曝險分析 (00981A)"""
    print("  [F] Industry Exposure (產業曝險)...")

    latest = dashboard.get('latest_holdings', {}).get(PRIMARY_ETF, {})
    stocks = latest.get('stocks', [])

    if not stocks:
        print("      No holdings data.")
        return []

    industry_data = defaultdict(lambda: {'weight': 0, 'stocks': []})

    for s in stocks:
        code = s['code']
        industry = INDUSTRY_MAP.get(code, '其他')
        industry_data[industry]['weight'] += s.get('weight', 0)
        industry_data[industry]['stocks'].append({
            'code': code,
            'name': s['name'],
            'weight': s.get('weight', 0),
        })

    result = []
    for industry, data in industry_data.items():
        top_stocks = sorted(data['stocks'], key=lambda x: x['weight'], reverse=True)[:5]
        result.append({
            'industry': industry,
            'weight': round(data['weight'], 2),
            'n_stocks': len(data['stocks']),
            'top_stocks': top_stocks,
        })

    result.sort(key=lambda x: x['weight'], reverse=True)
    print(f"      {len(result)} industries, top: {result[0]['industry']}={result[0]['weight']}%"
          if result else "      No industries")
    return result


# ═══════════════════════════════════════
# H. Holdings Overlap Heatmap (持倉重疊)
# ═══════════════════════════════════════

def calc_holdings_overlap(dashboard):
    """H. 持倉重疊分析"""
    print("  [H] Holdings Overlap Heatmap (持倉重疊)...")

    latest_holdings = dashboard.get('latest_holdings', {})
    etf_ids = [eid for eid in ETF_IDS if eid in latest_holdings]

    if len(etf_ids) < 2:
        print("      Not enough ETFs with data.")
        return {'matrix': [], 'etf_ids': etf_ids, 'shared_details': {}}

    # Build holdings maps
    holdings_map = {}
    for eid in etf_ids:
        stocks = latest_holdings[eid].get('stocks', [])
        holdings_map[eid] = {s['code']: s for s in stocks}

    n = len(etf_ids)
    matrix = [[0] * n for _ in range(n)]
    shared_details = {}

    for i in range(n):
        for j in range(n):
            eid_i = etf_ids[i]
            eid_j = etf_ids[j]
            codes_i = set(holdings_map[eid_i].keys())
            codes_j = set(holdings_map[eid_j].keys())
            shared = codes_i & codes_j
            matrix[i][j] = len(shared)

            if i < j and shared:
                key = f"{eid_i}_{eid_j}"
                details = []
                for code in shared:
                    si = holdings_map[eid_i][code]
                    sj = holdings_map[eid_j][code]
                    details.append({
                        'code': code,
                        'name': si.get('name', ''),
                        'weight_i': si.get('weight', 0),
                        'weight_j': sj.get('weight', 0),
                    })
                details.sort(key=lambda d: d['weight_i'] + d['weight_j'], reverse=True)
                shared_details[key] = details[:10]

    print(f"      {n}x{n} matrix built")
    return {
        'matrix': matrix,
        'etf_ids': etf_ids,
        'shared_details': shared_details,
    }


# ═══════════════════════════════════════
# I. Market Timing Score (經理人擇時能力)
# ═══════════════════════════════════════

def calc_timing_score(dashboard):
    """I. 經理人擇時能力評估"""
    print("  [I] Market Timing Score (經理人擇時能力)...")

    cash_series = dashboard.get('cash_series', [])
    if len(cash_series) < 12:
        print("      Not enough data for timing analysis.")
        return {
            'accuracy_5d': 0, 'accuracy_10d': 0,
            'correct_calls': 0, 'total_calls': 0,
            'recent_calls': [],
        }

    # Build TAIEX lookup from cash_series
    taiex_by_date = {}
    for cs in cash_series:
        if cs.get('taiex') is not None:
            taiex_by_date[cs['date']] = cs['taiex']

    dates_with_taiex = sorted(taiex_by_date.keys())
    if len(dates_with_taiex) < 12:
        print("      Not enough TAIEX data.")
        return {
            'accuracy_5d': 0, 'accuracy_10d': 0,
            'correct_calls': 0, 'total_calls': 0,
            'recent_calls': [],
        }

    # Build cash_pct by date
    cash_by_date = {}
    for cs in cash_series:
        cash_by_date[cs['date']] = cs.get('cash_pct', 0)

    # Evaluate timing: when cash changes significantly, check TAIEX response
    calls_5d = []
    calls_10d = []
    recent_calls = []

    for i in range(1, len(cash_series)):
        curr = cash_series[i]
        prev = cash_series[i - 1]
        cash_change = (curr.get('cash_pct', 0) or 0) - (prev.get('cash_pct', 0) or 0)

        # Only consider significant cash changes (>0.5%)
        if abs(cash_change) < 0.5:
            continue

        dt = curr['date']

        # Find TAIEX change 5d and 10d later
        dt_idx = None
        for idx, d in enumerate(dates_with_taiex):
            if d == dt:
                dt_idx = idx
                break
        if dt_idx is None:
            # Try finding closest date
            for idx, d in enumerate(dates_with_taiex):
                if d >= dt:
                    dt_idx = idx
                    break

        if dt_idx is None:
            continue

        taiex_now = taiex_by_date.get(dates_with_taiex[dt_idx])
        if taiex_now is None:
            continue

        # 5d change
        correct_5d = None
        taiex_change_5d = None
        if dt_idx + 5 < len(dates_with_taiex):
            taiex_5d = taiex_by_date.get(dates_with_taiex[dt_idx + 5])
            if taiex_5d is not None and taiex_now > 0:
                taiex_change_5d = round((taiex_5d - taiex_now) / taiex_now * 100, 2)
                # Defensive (cash up) -> TAIEX should go down
                # Aggressive (cash down) -> TAIEX should go up
                if cash_change > 0:
                    correct_5d = taiex_change_5d < 0
                else:
                    correct_5d = taiex_change_5d > 0
                calls_5d.append(correct_5d)

        # 10d change
        correct_10d = None
        taiex_change_10d = None
        if dt_idx + 10 < len(dates_with_taiex):
            taiex_10d = taiex_by_date.get(dates_with_taiex[dt_idx + 10])
            if taiex_10d is not None and taiex_now > 0:
                taiex_change_10d = round((taiex_10d - taiex_now) / taiex_now * 100, 2)
                if cash_change > 0:
                    correct_10d = taiex_change_10d < 0
                else:
                    correct_10d = taiex_change_10d > 0
                calls_10d.append(correct_10d)

        recent_calls.append({
            'date': dt,
            'cash_change': round(cash_change, 2),
            'direction': '防守 (增現金)' if cash_change > 0 else '進攻 (減現金)',
            'taiex_change_5d': taiex_change_5d,
            'taiex_change_10d': taiex_change_10d,
            'correct_5d': correct_5d,
            'correct_10d': correct_10d,
        })

    accuracy_5d = round(sum(1 for c in calls_5d if c) / max(len(calls_5d), 1) * 100, 1)
    accuracy_10d = round(sum(1 for c in calls_10d if c) / max(len(calls_10d), 1) * 100, 1)

    print(f"      {len(calls_5d)} timing calls, 5d accuracy={accuracy_5d}%, 10d accuracy={accuracy_10d}%")

    return {
        'accuracy_5d': accuracy_5d,
        'accuracy_10d': accuracy_10d,
        'correct_calls': sum(1 for c in calls_5d if c),
        'total_calls': len(calls_5d),
        'recent_calls': recent_calls[-20:],  # last 20 calls
    }


# ═══════════════════════════════════════
# J. 0050 Strategy + Market Weight Top 150
# ═══════════════════════════════════════

def fetch_taifex_rankings(limit=200):
    """從期交所抓取市值排名，回傳 [{rank, code, name}, ...]"""
    import requests
    print(f"  [J] Fetching TAIFEX rankings (top {limit})...")

    try:
        r = requests.get(TAIFEX_RANKING_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        encoding = r.apparent_encoding or 'big5'
        html_text = r.content.decode(encoding, errors='ignore')
    except Exception as e:
        print(f"      TAIFEX request failed: {e}")
        return []

    # Method 1: BeautifulSoup parsing
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, 'html.parser')
        rows = []
        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')
            if not tds:
                continue
            texts = [td.get_text(strip=True) for td in tds]
            rank, code, name = None, None, None
            for s in texts:
                if rank is None and re.fullmatch(r'\d+', s):
                    rank = int(s)
                elif rank and not code and re.fullmatch(r'\d{4}', s):
                    code = s
                elif rank and code and not name and not re.fullmatch(r'\d+', s):
                    name = s
                    break
            if rank and code and name:
                rows.append({'rank': rank, 'code': code, 'name': name})
        if rows:
            rows.sort(key=lambda x: x['rank'])
            print(f"      BS4 parsed: {len(rows[:limit])} stocks")
            return rows[:limit]
    except ImportError:
        print("      bs4 not available, trying pd.read_html fallback...")

    # Method 2: pandas fallback
    try:
        import io
        dfs = pd.read_html(io.StringIO(html_text))
        for df in dfs:
            cols = ''.join(str(c) for c in df.columns)
            if '排名' in cols and ('名稱' in cols or '代號' in cols):
                df.columns = [str(c).replace(' ', '') for c in df.columns]
                col_map = {}
                for c in df.columns:
                    if '排名' in c:
                        col_map[c] = '排名'
                    elif '代' in c:
                        col_map[c] = '股票代碼'
                    elif '名' in c:
                        col_map[c] = '股票名稱'
                df = df.rename(columns=col_map)
                df = df[pd.to_numeric(df['排名'], errors='coerce').notnull()]
                df['排名'] = df['排名'].astype(int)
                df['股票代碼'] = df['股票代碼'].astype(str).str.extract(r'(\d{4})')[0]
                df = df.sort_values('排名').head(limit)
                rows = [
                    {'rank': int(row['排名']), 'code': row['股票代碼'], 'name': row['股票名稱']}
                    for _, row in df.iterrows()
                ]
                print(f"      pandas parsed: {len(rows)} stocks")
                return rows
    except Exception as e:
        print(f"      pandas fallback failed: {e}")

    return []


def fetch_etf_holdings(etf_code='0050'):
    """從 MoneyDJ 抓取 ETF 成分股名稱，回傳 set"""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    url = MONEYDJ_ETF_URL.format(etf_code)
    print(f"  [J] Fetching {etf_code} holdings from MoneyDJ...")

    try:
        hdrs = {**HEADERS,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.moneydj.com/'}
        r = requests.get(url, headers=hdrs, timeout=15, verify=False)
        r.encoding = r.apparent_encoding or 'utf-8'
        dfs = pd.read_html(io.StringIO(r.text))

        names = set()
        for df in dfs:
            cols = [str(c[-1] if isinstance(df.columns, pd.MultiIndex) else c).strip()
                    for c in df.columns]
            df.columns = cols
            target_col = next((c for c in cols if '名稱' in c), None)
            if target_col:
                for v in df[target_col].astype(str).str.strip():
                    if v and v != 'nan':
                        names.add(v)

        print(f"      {etf_code} holdings: {len(names)} stocks")
        return names
    except Exception as e:
        print(f"      MoneyDJ fetch failed: {e}")
        return set()


def fetch_stock_quotes_batch(codes):
    """用 Yahoo Finance 批次抓取股價、漲跌、成交量、市值"""
    import requests as _req

    if not codes:
        return {}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }

    result = {}
    print(f"      Fetching quotes for {len(codes)} stocks...")

    for code in codes:
        symbol = f"{code}.TW"
        try:
            r = _req.get(
                f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
                f'?range=5d&interval=1d&includePrePost=false',
                headers=headers, timeout=10
            )
            if r.status_code != 200:
                continue

            chart = r.json().get('chart', {}).get('result', [{}])[0]
            meta = chart.get('meta', {})
            quote = chart.get('indicators', {}).get('quote', [{}])[0]

            closes = [c for c in (quote.get('close') or []) if c is not None]
            volumes = [v for v in (quote.get('volume') or []) if v is not None]

            if not closes:
                continue

            price = round(closes[-1], 2)
            prev_close = round(closes[-2], 2) if len(closes) >= 2 else meta.get('chartPreviousClose', price)
            change = round(price - prev_close, 2)
            change_pct = round(change / prev_close * 100, 2) if prev_close else 0
            volume = volumes[-1] if volumes else 0
            turnover = int(price * volume) if volume else 0
            market_cap = meta.get('regularMarketPrice', price) * meta.get('regularMarketVolume', 0)

            # 從 meta 取市值（若有）
            # Yahoo chart API meta 沒有直接的 marketCap，用另一種方式
            result[code] = {
                'price': price,
                'prev_close': prev_close,
                'change': change,
                'change_pct': change_pct,
                'volume': volume,
                'turnover': turnover,
            }

            time.sleep(0.3)  # rate limit

        except Exception as e:
            print(f"        {code} quote failed: {e}")

    print(f"      Got quotes for {len(result)}/{len(codes)} stocks")
    return result


def _enrich_stocks_with_quotes(stocks, quotes):
    """將報價資料合併到股票列表"""
    for s in stocks:
        q = quotes.get(s['code'], {})
        s['price'] = q.get('price', '-')
        s['change'] = q.get('change', '-')
        s['change_pct'] = q.get('change_pct', '-')
        s['volume'] = q.get('volume', 0)
        s['turnover'] = q.get('turnover', 0)
        s['link'] = f"https://tw.stock.yahoo.com/quote/{s['code']}"
    return stocks


def calc_0050_and_market_weight():
    """計算 0050 納入/剔除 + 市值權重 Top 150"""
    print("  [J] 0050 Strategy + Market Weight Top 150...")

    rankings = fetch_taifex_rankings(limit=200)
    time.sleep(1)
    holdings_0050 = fetch_etf_holdings('0050')

    # --- 0050 Inclusion/Exclusion ---
    potential_in = []
    potential_out = []

    if rankings and holdings_0050:
        for stock in rankings[:100]:
            in_0050 = stock['name'] in holdings_0050
            if stock['rank'] <= THRESHOLD_0050_IN and not in_0050:
                potential_in.append(stock.copy())
            elif stock['rank'] > THRESHOLD_0050_OUT and in_0050:
                potential_out.append(stock.copy())

    print(f"      0050: {len(potential_in)} potential in, {len(potential_out)} potential out")

    # --- Enrich 0050 candidates with quotes ---
    candidate_codes = [s['code'] for s in potential_in + potential_out]
    if candidate_codes:
        quotes = fetch_stock_quotes_batch(candidate_codes)
        potential_in = _enrich_stocks_with_quotes(potential_in, quotes)
        potential_out = _enrich_stocks_with_quotes(potential_out, quotes)

    strategy_0050 = {
        'potential_in': potential_in,
        'potential_out': potential_out,
    }

    # --- Market Weight Top 150 ---
    top150 = [s.copy() for s in rankings[:150]] if rankings else []
    print(f"      Market Weight: {len(top150)} stocks")

    # Enrich top 150 with quotes (batch in chunks to avoid rate limit)
    if top150:
        top150_codes = [s['code'] for s in top150]
        all_quotes = {}
        for i in range(0, len(top150_codes), 30):
            chunk = top150_codes[i:i+30]
            chunk_quotes = fetch_stock_quotes_batch(chunk)
            all_quotes.update(chunk_quotes)
            if i + 30 < len(top150_codes):
                time.sleep(1)
        top150 = _enrich_stocks_with_quotes(top150, all_quotes)

    market_weight = {
        'stocks': top150,
    }

    return strategy_0050, market_weight


# ═══════════════════════════════════════
# K. Risk Signals (宏觀風險訊號)
# ═══════════════════════════════════════

def fetch_indices_history():
    """抓取 9 個風險指標的 60 天歷史，合併到 indices_history.json"""
    import requests as _req

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }

    # Load existing history
    history = {}
    if INDICES_HISTORY_PATH.exists():
        try:
            history = load_json(INDICES_HISTORY_PATH)
            print(f"  [K] Loaded existing history: {len(history)} symbols")
        except Exception:
            pass

    print("  [K] Fetching indices history (3 months)...")

    for key, symbol in RISK_SYMBOLS.items():
        try:
            url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
                   f'?range=3mo&interval=1d')
            r = _req.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"      {key}: HTTP {r.status_code}")
                continue

            chart = r.json().get('chart', {}).get('result', [{}])[0]
            timestamps = chart.get('timestamp', [])
            closes = chart.get('indicators', {}).get('quote', [{}])[0].get('close', [])

            if not timestamps or not closes:
                print(f"      {key}: no data")
                continue

            new_records = {}
            for ts, c in zip(timestamps, closes):
                if c is not None:
                    dt = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
                    new_records[dt] = round(c, 4)

            # Merge with existing (keep latest 90 days)
            existing = {r['date']: r['close'] for r in history.get(key, [])}
            existing.update(new_records)

            sorted_dates = sorted(existing.keys())[-90:]
            history[key] = [{'date': d, 'close': existing[d]} for d in sorted_dates]

            print(f"      {key}: {len(history[key])} days")
            time.sleep(0.3)

        except Exception as e:
            print(f"      {key} failed: {e}")

    # Append Fear & Greed (from CNN API, today only)
    try:
        cnn_headers = {**headers, 'Referer': 'https://edition.cnn.com/markets/fear-and-greed'}
        r = _req.get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
                     headers=cnn_headers, timeout=10)
        if r.status_code == 200:
            fg = r.json().get('fear_and_greed', {})
            if fg.get('score') is not None:
                today = datetime.now().strftime('%Y-%m-%d')
                existing_fg = {r['date']: r['close'] for r in history.get('fear_greed', [])}
                existing_fg[today] = round(fg['score'], 1)
                sorted_dates = sorted(existing_fg.keys())[-90:]
                history['fear_greed'] = [{'date': d, 'close': existing_fg[d]} for d in sorted_dates]
                print(f"      fear_greed: {len(history['fear_greed'])} days")
    except Exception as e:
        print(f"      fear_greed failed: {e}")

    # Save history
    save_json(INDICES_HISTORY_PATH, history)
    print(f"  [K] History saved: {len(history)} symbols")

    return history


def _slope_20d(values):
    """計算最近 20 天的線性回歸斜率（每日平均變化量）"""
    import numpy as np
    recent = values[-20:] if len(values) >= 20 else values
    if len(recent) < 5:
        return 0.0
    x = np.arange(len(recent), dtype=float)
    y = np.array(recent, dtype=float)
    slope = np.polyfit(x, y, 1)[0]
    return round(float(slope), 4)


def _ratio_series(hist_a, hist_b):
    """計算兩個序列的比值序列（按日期對齊）"""
    map_b = {r['date']: r['close'] for r in hist_b}
    result = []
    for r in hist_a:
        b_val = map_b.get(r['date'])
        if b_val and b_val != 0:
            result.append({'date': r['date'], 'close': round(r['close'] / b_val, 6)})
    return result


def calc_risk_signals(history):
    """根據研究報告計算 8 個風險訊號 + 總分"""
    print("  [K] Calculating risk signals...")

    signals = []

    def _get_closes(key):
        return [r['close'] for r in history.get(key, [])]

    def _latest(key):
        data = history.get(key, [])
        return data[-1]['close'] if data else None

    # 1. VIX 趨勢
    vix_vals = _get_closes('vix')
    vix_slope = _slope_20d(vix_vals)
    vix_latest = _latest('vix')
    if vix_slope > 0.3 or (vix_latest and vix_latest > 30):
        vix_signal = 'red'
    elif vix_slope > 0.1 or (vix_latest and vix_latest > 25):
        vix_signal = 'yellow'
    else:
        vix_signal = 'green'
    signals.append({
        'name': 'VIX 趨勢', 'key': 'vix', 'value': vix_latest,
        'slope_20d': vix_slope, 'signal': vix_signal,
        'desc': f'20日斜率 {vix_slope:+.2f}/日' + (f'，當前 {vix_latest:.1f}' if vix_latest else ''),
        'theory': '波動率的緩步墊高比絕對數值更重要（研究重要度 13.3%）',
    })

    # 2. SPY/JPY 套利平倉壓力
    spy_jpy = _ratio_series(history.get('spy', []), history.get('jpy', []))
    spy_jpy_vals = [r['close'] for r in spy_jpy]
    spy_jpy_slope = _slope_20d(spy_jpy_vals)
    if spy_jpy_slope < -0.01:
        sj_signal = 'red'
    elif spy_jpy_slope < -0.003:
        sj_signal = 'yellow'
    else:
        sj_signal = 'green'
    signals.append({
        'name': '套利平倉壓力', 'key': 'spy_jpy', 'value': round(spy_jpy_vals[-1], 4) if spy_jpy_vals else None,
        'slope_20d': spy_jpy_slope, 'signal': sj_signal,
        'desc': f'SPY/JPY 20日斜率 {spy_jpy_slope:+.4f}',
        'theory': '日圓套利平倉是美股崩盤最強領先指標（研究重要度 19.9%）',
    })

    # 3. HYG/TLT 流動性枯竭
    hyg_tlt = _ratio_series(history.get('hyg', []), history.get('tlt', []))
    hyg_tlt_vals = [r['close'] for r in hyg_tlt]
    hyg_tlt_slope = _slope_20d(hyg_tlt_vals)
    if hyg_tlt_slope < -0.003:
        ht_signal = 'red'
    elif hyg_tlt_slope < -0.001:
        ht_signal = 'yellow'
    else:
        ht_signal = 'green'
    signals.append({
        'name': '流動性枯竭', 'key': 'hyg_tlt', 'value': round(hyg_tlt_vals[-1], 4) if hyg_tlt_vals else None,
        'slope_20d': hyg_tlt_slope, 'signal': ht_signal,
        'desc': f'HYG/TLT 20日斜率 {hyg_tlt_slope:+.4f}',
        'theory': '資金從垃圾債撤回國債的速度反映流動性枯竭（研究重要度 12.5%）',
    })

    # 4. 美元壓力
    dxy_vals = _get_closes('dxy')
    dxy_slope = _slope_20d(dxy_vals)
    if dxy_slope > 0.3:
        dxy_signal = 'red'
    elif dxy_slope > 0.1:
        dxy_signal = 'yellow'
    else:
        dxy_signal = 'green'
    signals.append({
        'name': '美元壓力', 'key': 'dxy', 'value': _latest('dxy'),
        'slope_20d': dxy_slope, 'signal': dxy_signal,
        'desc': f'DXY 20日斜率 {dxy_slope:+.2f}/日',
        'theory': '美元急升對新興市場與資金流造成壓力',
    })

    # 5. 公債殖利率
    us10y_vals = _get_closes('us10y')
    us10y_slope = _slope_20d(us10y_vals)
    if us10y_slope > 0.05:
        us10y_signal = 'red'
    elif us10y_slope > 0.02:
        us10y_signal = 'yellow'
    else:
        us10y_signal = 'green'
    signals.append({
        'name': '公債殖利率', 'key': 'us10y', 'value': _latest('us10y'),
        'slope_20d': us10y_slope, 'signal': us10y_signal,
        'desc': f'US10Y 20日斜率 {us10y_slope:+.3f}/日',
        'theory': '殖利率快速上升代表債券拋售、資金成本攀升',
    })

    # 6. 恐懼貪婪
    fg_latest = _latest('fear_greed')
    if fg_latest is not None:
        if fg_latest < 25:
            fg_signal = 'red'
        elif fg_latest < 40:
            fg_signal = 'yellow'
        else:
            fg_signal = 'green'
    else:
        fg_signal = 'gray'
    signals.append({
        'name': '恐懼貪婪', 'key': 'fear_greed', 'value': fg_latest,
        'slope_20d': _slope_20d(_get_closes('fear_greed')),
        'signal': fg_signal,
        'desc': f'CNN Fear & Greed: {fg_latest}' if fg_latest else '無資料',
        'theory': '極端恐懼往往伴隨市場超賣，但也可能繼續下跌',
    })

    # 7. 黃金避險
    gold_vals = _get_closes('gold')
    gold_slope = _slope_20d(gold_vals)
    if gold_slope > 15:
        gold_signal = 'red'
    elif gold_slope > 5:
        gold_signal = 'yellow'
    else:
        gold_signal = 'green'
    signals.append({
        'name': '黃金避險', 'key': 'gold', 'value': _latest('gold'),
        'slope_20d': gold_slope, 'signal': gold_signal,
        'desc': f'Gold 20日斜率 {gold_slope:+.1f}/日',
        'theory': '金價急漲代表避險資金湧入，風險偏好降低',
    })

    # 8. 油價壓力
    oil_vals = _get_closes('oil')
    oil_slope = _slope_20d(oil_vals)
    if oil_slope > 2:
        oil_signal = 'red'
    elif oil_slope > 0.5:
        oil_signal = 'yellow'
    else:
        oil_signal = 'green'
    signals.append({
        'name': '油價壓力', 'key': 'oil', 'value': _latest('oil'),
        'slope_20d': oil_slope, 'signal': oil_signal,
        'desc': f'Oil 20日斜率 {oil_slope:+.2f}/日',
        'theory': '油價急漲推升通膨預期與企業成本壓力',
    })

    # Total score: red=2, yellow=1, max=16 -> scale to 0-10
    raw_score = sum(2 if s['signal'] == 'red' else 1 if s['signal'] == 'yellow' else 0 for s in signals)
    score = round(raw_score / 16 * 10, 1)
    if score >= 7:
        level = 'high'
    elif score >= 4:
        level = 'medium'
    else:
        level = 'low'

    n_red = sum(1 for s in signals if s['signal'] == 'red')
    n_yellow = sum(1 for s in signals if s['signal'] == 'yellow')
    n_green = sum(1 for s in signals if s['signal'] == 'green')
    print(f"      Score: {score}/10 ({level}) | Red:{n_red} Yellow:{n_yellow} Green:{n_green}")

    # Build sparkline history (last 30 days for each key)
    spark_history = {}
    for key in ['vix', 'dxy', 'oil', 'gold', 'us10y', 'fear_greed']:
        data = history.get(key, [])[-30:]
        spark_history[key] = data

    # Add ratio sparklines
    spark_history['spy_jpy'] = spy_jpy[-30:] if spy_jpy else []
    spark_history['hyg_tlt'] = hyg_tlt[-30:] if hyg_tlt else []

    return {
        'score': score,
        'max_score': 10,
        'level': level,
        'n_red': n_red,
        'n_yellow': n_yellow,
        'n_green': n_green,
        'signals': signals,
        'history': spark_history,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


# ═══════════════════════════════════════
# Main
# ═══════════════════════════════════════

def _fetch_yahoo_quote(symbol, headers):
    """Fetch a single symbol from Yahoo Finance. Returns (price, prev_close, change, change_pct) or Nones."""
    import requests
    try:
        r = requests.get(
            f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d',
            headers=headers, timeout=10
        )
        if r.status_code == 200:
            res = r.json().get('chart', {}).get('result', [{}])[0]
            closes = res.get('indicators', {}).get('quote', [{}])[0].get('close', [])
            # Filter out None values
            closes = [c for c in closes if c is not None]
            if len(closes) >= 2:
                price = round(closes[-1], 2)
                prev = round(closes[-2], 2)
                chg = round(price - prev, 2)
                chg_pct = round((price - prev) / prev * 100, 2) if prev else 0
                return price, prev, chg, chg_pct
            elif closes:
                price = round(closes[-1], 2)
                return price, None, None, None
    except Exception as e:
        print(f"  [MKT] Yahoo fetch {symbol} failed: {e}")
    return None, None, None, None


def fetch_market_indices_live():
    """Fetch VIX, VIXTWN, CNN Fear & Greed, DXY, Oil, Gold, US 10Y Yield."""
    import requests, re
    result = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }

    print("  [MKT] Fetching market indices...")

    # ── Yahoo Finance symbols (all with change data) ──
    yahoo_symbols = {
        'vix':    {'symbol': '%5EVIX',    'label': 'VIX S&P500'},
        'vixtwn': {'symbol': '%5ETWVIX',  'label': 'VIX 台灣'},
        'dxy':    {'symbol': 'DX-Y.NYB',  'label': 'DXY 美元指數'},
        'oil':    {'symbol': 'CL%3DF',    'label': 'WTI 原油'},
        'gold':   {'symbol': 'GC%3DF',    'label': '黃金'},
        'us10y':  {'symbol': '%5ETNX',    'label': 'US 10Y 殖利率'},
    }

    for key, info in yahoo_symbols.items():
        price, prev, chg, chg_pct = _fetch_yahoo_quote(info['symbol'], headers)
        if price is not None:
            result[key] = price
            if chg is not None:
                result[f'{key}_prev'] = prev
                result[f'{key}_chg'] = chg
                result[f'{key}_chg_pct'] = chg_pct
            print(f"  [MKT] {info['label']}: {price}" + (f" ({chg:+.2f}, {chg_pct:+.2f}%)" if chg is not None else ""))

    # ── VIXTWN fallback: TAIFEX website if Yahoo failed ──
    if 'vixtwn' not in result:
        try:
            r = requests.get('https://www.taifex.com.tw/cht/9/VIXQuote',
                             headers={'User-Agent': headers['User-Agent']}, timeout=10)
            if r.status_code == 200:
                matches = re.findall(r'>(\d{1,3}\.\d{2})<', r.text)
                if matches:
                    result['vixtwn'] = float(matches[0])
                    print(f"  [MKT] VIX 台灣 (TAIFEX fallback): {result['vixtwn']}")
                else:
                    print("  [MKT] VIXTWN: no data found on page")
        except Exception as e:
            print(f"  [MKT] VIXTWN fallback failed: {e}")

    # ── CNN Fear & Greed (with previous day change) ──
    try:
        cnn_headers = {**headers, 'Referer': 'https://edition.cnn.com/markets/fear-and-greed'}
        r = requests.get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
                         headers=cnn_headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            fg = data.get('fear_and_greed', {})
            if fg.get('score') is not None:
                score = round(fg['score'], 1)
                result['fear_greed'] = score
                result['fear_greed_rating'] = fg.get('rating', '')
                # Get previous close for change calculation
                prev_close = fg.get('previous_close')
                if prev_close is not None:
                    prev_val = round(prev_close, 1)
                    result['fear_greed_prev'] = prev_val
                    result['fear_greed_chg'] = round(score - prev_val, 1)
                    print(f"  [MKT] CNN Fear & Greed: {score} ({result['fear_greed_rating']}) chg={result['fear_greed_chg']:+.1f}")
                else:
                    # Try previous_1_week or timeline data
                    prev_1d = data.get('fear_and_greed_historical', {}).get('data', [])
                    if len(prev_1d) >= 2:
                        prev_val = round(prev_1d[-2].get('y', prev_1d[-2].get('score', score)), 1)
                        result['fear_greed_prev'] = prev_val
                        result['fear_greed_chg'] = round(score - prev_val, 1)
                        print(f"  [MKT] CNN Fear & Greed: {score} ({result['fear_greed_rating']}) chg={result['fear_greed_chg']:+.1f}")
                    else:
                        print(f"  [MKT] CNN Fear & Greed: {score} ({result['fear_greed_rating']})")
        else:
            print(f"  [MKT] CNN Fear & Greed: status {r.status_code}")
    except Exception as e:
        print(f"  [MKT] Fear & Greed fetch failed: {e}")

    return result


def main():
    print("=" * 60)
    print("Wolf Pack Strategy Engine")
    print("=" * 60)
    print(f"  Platform: {platform.system()}")
    print(f"  Data dir: {DATA_DIR}")
    print(f"  Dashboard: {DASHBOARD_PATH}")
    print(f"  ETF Pages: {ETF_PAGES_PATH}")
    print(f"  Output: {STRATEGY_PATH}")
    print()

    # Load input data
    print("Loading data...")
    if not DASHBOARD_PATH.exists():
        print(f"  ERROR: {DASHBOARD_PATH} not found!")
        sys.exit(1)
    if not ETF_PAGES_PATH.exists():
        print(f"  ERROR: {ETF_PAGES_PATH} not found!")
        sys.exit(1)

    dashboard = load_json(DASHBOARD_PATH)
    etf_pages = load_json(ETF_PAGES_PATH)
    print(f"  Dashboard: report_date={dashboard.get('report_date')}")
    print(f"  ETF Pages: {len(etf_pages)} ETFs")
    print()

    strategy = {
        'report_date': dashboard.get('report_date'),
        'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # ── B. Manager Style Analysis ──
    try:
        strategy['manager_styles'] = calc_manager_styles(etf_pages)
    except Exception as e:
        print(f"  [B] ERROR: {e}")
        strategy['manager_styles'] = {}

    # ── C. Consensus Trend ──
    try:
        strategy['consensus_trends'] = calc_consensus_trends(dashboard, etf_pages)
    except Exception as e:
        print(f"  [C] ERROR: {e}")
        strategy['consensus_trends'] = []

    # ── D. Velocity Indicator ──
    try:
        strategy['velocity'] = calc_velocity(dashboard)
    except Exception as e:
        print(f"  [D] ERROR: {e}")
        strategy['velocity'] = []

    # ── I. Market Timing Score ──
    try:
        strategy['timing_score'] = calc_timing_score(dashboard)
    except Exception as e:
        print(f"  [I] ERROR: {e}")
        strategy['timing_score'] = {}

    # ── E. Action Recommendation ──
    try:
        strategy['recommendations'] = calc_recommendations(dashboard, strategy.get('velocity', []))
    except Exception as e:
        print(f"  [E] ERROR: {e}")
        strategy['recommendations'] = []

    # ── F. Industry Exposure ──
    try:
        strategy['industry_exposure'] = calc_industry_exposure(dashboard)
    except Exception as e:
        print(f"  [F] ERROR: {e}")
        strategy['industry_exposure'] = []

    # ── H. Holdings Overlap ──
    try:
        strategy['holdings_overlap'] = calc_holdings_overlap(dashboard)
    except Exception as e:
        print(f"  [H] ERROR: {e}")
        strategy['holdings_overlap'] = {}

    # ── Market Indices (VIX, VIXTWN, Fear & Greed) ──
    try:
        strategy['market_indices'] = fetch_market_indices_live()
    except Exception as e:
        print(f"  [MKT] ERROR: {e}")
        strategy['market_indices'] = {}

    # ── J. 0050 Strategy + Market Weight Top 150 ──
    try:
        s0050, mw150 = calc_0050_and_market_weight()
        strategy['strategy_0050'] = s0050
        strategy['market_weight_top150'] = mw150
    except Exception as e:
        print(f"  [J] ERROR: {e}")
        strategy['strategy_0050'] = {"potential_in": [], "potential_out": []}
        strategy['market_weight_top150'] = {"stocks": []}

    # ── K. Risk Signals ──
    try:
        indices_hist = fetch_indices_history()
        strategy['risk_signals'] = calc_risk_signals(indices_hist)
    except Exception as e:
        print(f"  [K] ERROR: {e}")
        strategy['risk_signals'] = {"score": 0, "signals": [], "history": {}}

    # ── A. Signal Backtest (last, because it fetches from API) ──
    try:
        strategy['signal_backtest'] = calc_signal_backtest(dashboard)
    except Exception as e:
        print(f"  [A] ERROR: {e}")
        strategy['signal_backtest'] = {'summary': {}, 'by_type': {}, 'signals': []}

    # ── Save output ──
    print()
    print("Saving strategy.json...")
    strategy = clean(strategy)
    save_json(STRATEGY_PATH, strategy)
    sz = STRATEGY_PATH.stat().st_size
    print(f"  strategy.json: {sz:,} bytes ({sz / 1024:.0f} KB)")
    print()
    print("Done!")


if __name__ == '__main__':
    main()
