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
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

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
