#!/usr/bin/env python3
"""
Macro Signal Agent — 宏觀風險訊號計算
=======================================
接收 Data Agent 的資料 + Validator 的驗證結果，
計算 8 個風險訊號（速度/加速度/統計機率）、0050 策略、市值權重。

標準介面：run(data, validation) → {status, duration_ms, risk_signals, strategy_0050, market_weight_top150, warnings}
"""

import time
from datetime import datetime

THRESHOLD_0050_IN = 40
THRESHOLD_0050_OUT = 60


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] [SignalAgent] {msg}")


# ── Math Utilities ──

def _slope(values, window=20):
    """線性回歸斜率（一階導數：速度）"""
    import numpy as np
    recent = values[-window:] if len(values) >= window else values
    if len(recent) < 5:
        return 0.0
    x = np.arange(len(recent), dtype=float)
    y = np.array(recent, dtype=float)
    slope = np.polyfit(x, y, 1)[0]
    return round(float(slope), 4)


def _acceleration(values):
    """加速度（二階導數）：近 5 日斜率 vs 前 5 日斜率"""
    if len(values) < 15:
        return 0.0, 'stable'
    slope_recent = _slope(values, 5)
    slope_prior = _slope(values[-10:-5], 5)
    accel = round(slope_recent - slope_prior, 4)
    if abs(accel) < abs(slope_recent) * 0.1:
        phase = 'stable'
    elif (slope_recent > 0 and accel > 0) or (slope_recent < 0 and accel < 0):
        phase = 'accelerating'
    else:
        phase = 'decelerating'
    return accel, phase


def _regime_probability(values, current_slope, window=60):
    """統計在過去 window 天內，斜率達到當前水準的出現頻率"""
    if len(values) < 25:
        return None
    slopes = []
    for i in range(20, min(len(values), window + 20)):
        s = _slope(values[i-20:i], 20)
        slopes.append(s)
    if not slopes:
        return None
    abs_current = abs(current_slope)
    extreme_count = sum(1 for s in slopes if abs(s) >= abs_current)
    return round(extreme_count / len(slopes) * 100, 1)


def _ratio_series(hist_a, hist_b):
    """計算兩個序列的比值序列"""
    map_b = {r['date']: r['close'] for r in hist_b}
    result = []
    for r in hist_a:
        b_val = map_b.get(r['date'])
        if b_val and b_val != 0:
            result.append({'date': r['date'], 'close': round(r['close'] / b_val, 6)})
    return result


# ── Risk Signal Calculation ──

def calc_risk_signals(history, validator_warnings=None):
    """計算 8 個風險訊號 + 加速度 + 統計機率 + 總分"""
    log("Calculating risk signals...")

    # Build set of unreliable symbols from validator
    unreliable = set()
    if validator_warnings:
        for w in validator_warnings:
            if w.get('level') == 'ERROR':
                for sym in w.get('symbol', '').split(','):
                    unreliable.add(sym.strip())

    signals = []

    def _get_closes(key):
        return [r['close'] for r in history.get(key, [])]

    def _latest(key):
        data = history.get(key, [])
        return data[-1]['close'] if data else None

    def _enrich(sig, vals):
        accel, phase = _acceleration(vals)
        sig['accel'] = accel
        sig['phase'] = phase
        phase_labels = {'accelerating': '加速惡化中', 'decelerating': '趨緩/好轉中', 'stable': '持平'}
        sig['phase_label'] = phase_labels.get(phase, phase)
        sig['extremity_pct'] = _regime_probability(vals, sig['slope_20d'])
        sig['reliable'] = sig['key'] not in unreliable
        return sig

    # 1. VIX 趨勢
    vix_vals = _get_closes('vix')
    vix_slope = _slope(vix_vals, 20)
    vix_latest = _latest('vix')
    if vix_slope > 0.3 or (vix_latest and vix_latest > 30):
        vix_sig = 'red'
    elif vix_slope > 0.1 or (vix_latest and vix_latest > 25):
        vix_sig = 'yellow'
    else:
        vix_sig = 'green'
    signals.append(_enrich({
        'name': 'VIX 趨勢', 'key': 'vix', 'value': vix_latest,
        'slope_20d': vix_slope, 'signal': vix_sig,
        'desc': f'速度 {vix_slope:+.2f}/日' + (f' | 當前 {vix_latest:.1f}' if vix_latest else ''),
        'theory': '波動率的緩步墊高比絕對數值更重要（研究重要度 13.3%）',
    }, vix_vals))

    # 2. SPY/JPY 套利平倉壓力
    spy_jpy = _ratio_series(history.get('spy', []), history.get('jpy', []))
    spy_jpy_vals = [r['close'] for r in spy_jpy]
    spy_jpy_slope = _slope(spy_jpy_vals, 20)
    if spy_jpy_slope < -0.01:
        sj_sig = 'red'
    elif spy_jpy_slope < -0.003:
        sj_sig = 'yellow'
    else:
        sj_sig = 'green'
    signals.append(_enrich({
        'name': '套利平倉壓力', 'key': 'spy_jpy', 'value': round(spy_jpy_vals[-1], 4) if spy_jpy_vals else None,
        'slope_20d': spy_jpy_slope, 'signal': sj_sig,
        'desc': f'SPY/JPY 速度 {spy_jpy_slope:+.4f}',
        'theory': '日圓套利平倉是美股崩盤最強領先指標（研究重要度 19.9%）',
    }, spy_jpy_vals))

    # 3. HYG/TLT 流動性枯竭
    hyg_tlt = _ratio_series(history.get('hyg', []), history.get('tlt', []))
    hyg_tlt_vals = [r['close'] for r in hyg_tlt]
    hyg_tlt_slope = _slope(hyg_tlt_vals, 20)
    if hyg_tlt_slope < -0.003:
        ht_sig = 'red'
    elif hyg_tlt_slope < -0.001:
        ht_sig = 'yellow'
    else:
        ht_sig = 'green'
    signals.append(_enrich({
        'name': '流動性枯竭', 'key': 'hyg_tlt', 'value': round(hyg_tlt_vals[-1], 4) if hyg_tlt_vals else None,
        'slope_20d': hyg_tlt_slope, 'signal': ht_sig,
        'desc': f'HYG/TLT 速度 {hyg_tlt_slope:+.4f}',
        'theory': '資金從垃圾債撤回國債的速度反映流動性枯竭（研究重要度 12.5%）',
    }, hyg_tlt_vals))

    # 4. 美元壓力
    dxy_vals = _get_closes('dxy')
    dxy_slope = _slope(dxy_vals, 20)
    if dxy_slope > 0.3:
        dxy_sig = 'red'
    elif dxy_slope > 0.1:
        dxy_sig = 'yellow'
    else:
        dxy_sig = 'green'
    signals.append(_enrich({
        'name': '美元壓力', 'key': 'dxy', 'value': _latest('dxy'),
        'slope_20d': dxy_slope, 'signal': dxy_sig,
        'desc': f'DXY 速度 {dxy_slope:+.2f}/日',
        'theory': '美元急升對新興市場與資金流造成壓力',
    }, dxy_vals))

    # 5. 公債殖利率
    us10y_vals = _get_closes('us10y')
    us10y_slope = _slope(us10y_vals, 20)
    if us10y_slope > 0.05:
        us10y_sig = 'red'
    elif us10y_slope > 0.02:
        us10y_sig = 'yellow'
    else:
        us10y_sig = 'green'
    signals.append(_enrich({
        'name': '公債殖利率', 'key': 'us10y', 'value': _latest('us10y'),
        'slope_20d': us10y_slope, 'signal': us10y_sig,
        'desc': f'US10Y 速度 {us10y_slope:+.3f}/日',
        'theory': '殖利率快速上升代表債券拋售、資金成本攀升',
    }, us10y_vals))

    # 6. 恐懼貪婪
    fg_vals = _get_closes('fear_greed')
    fg_latest = _latest('fear_greed')
    fg_slope = _slope(fg_vals, 20)
    if fg_latest is not None:
        fg_sig = 'red' if fg_latest < 25 else 'yellow' if fg_latest < 40 else 'green'
    else:
        fg_sig = 'gray'
    signals.append(_enrich({
        'name': '恐懼貪婪', 'key': 'fear_greed', 'value': fg_latest,
        'slope_20d': fg_slope, 'signal': fg_sig,
        'desc': f'Fear & Greed: {fg_latest}' if fg_latest else '無資料',
        'theory': '極端恐懼往往伴隨市場超賣，但也可能繼續下跌',
    }, fg_vals))

    # 7. 黃金避險
    gold_vals = _get_closes('gold')
    gold_slope = _slope(gold_vals, 20)
    if gold_slope > 15:
        gold_sig = 'red'
    elif gold_slope > 5:
        gold_sig = 'yellow'
    else:
        gold_sig = 'green'
    signals.append(_enrich({
        'name': '黃金避險', 'key': 'gold', 'value': _latest('gold'),
        'slope_20d': gold_slope, 'signal': gold_sig,
        'desc': f'Gold 速度 {gold_slope:+.1f}/日',
        'theory': '金價急漲代表避險資金湧入，風險偏好降低',
    }, gold_vals))

    # 8. 油價壓力
    oil_vals = _get_closes('oil')
    oil_slope = _slope(oil_vals, 20)
    if oil_slope > 2:
        oil_sig = 'red'
    elif oil_slope > 0.5:
        oil_sig = 'yellow'
    else:
        oil_sig = 'green'
    signals.append(_enrich({
        'name': '油價壓力', 'key': 'oil', 'value': _latest('oil'),
        'slope_20d': oil_slope, 'signal': oil_sig,
        'desc': f'Oil 速度 {oil_slope:+.2f}/日',
        'theory': '油價急漲推升通膨預期與企業成本壓力',
    }, oil_vals))

    # Total score
    raw_score = sum(2 if s['signal'] == 'red' else 1 if s['signal'] == 'yellow' else 0 for s in signals)
    score = round(raw_score / 16 * 10, 1)
    level = 'high' if score >= 7 else 'medium' if score >= 4 else 'low'

    n_red = sum(1 for s in signals if s['signal'] == 'red')
    n_yellow = sum(1 for s in signals if s['signal'] == 'yellow')
    n_green = sum(1 for s in signals if s['signal'] == 'green')
    log(f"  Score: {score}/10 ({level}) | Red:{n_red} Yellow:{n_yellow} Green:{n_green}")

    # Sparkline history
    spark_history = {}
    for key in ['vix', 'dxy', 'oil', 'gold', 'us10y', 'fear_greed']:
        spark_history[key] = (history.get(key, []))[-30:]
    spark_history['spy_jpy'] = spy_jpy[-30:] if spy_jpy else []
    spark_history['hyg_tlt'] = hyg_tlt[-30:] if hyg_tlt else []

    return {
        'score': score, 'max_score': 10, 'level': level,
        'n_red': n_red, 'n_yellow': n_yellow, 'n_green': n_green,
        'signals': signals,
        'history': spark_history,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


# ── 0050 Strategy ──

def calc_0050_strategy(rankings, holdings_0050):
    """計算 0050 納入/剔除候選"""
    log("Calculating 0050 strategy...")
    holdings_set = set(holdings_0050) if isinstance(holdings_0050, list) else holdings_0050

    potential_in = []
    potential_out = []

    if rankings and holdings_set:
        for stock in rankings[:100]:
            in_0050 = stock['name'] in holdings_set
            if stock['rank'] <= THRESHOLD_0050_IN and not in_0050:
                potential_in.append(stock.copy())
            elif stock['rank'] > THRESHOLD_0050_OUT and in_0050:
                potential_out.append(stock.copy())

    log(f"  0050: {len(potential_in)} potential in, {len(potential_out)} potential out")
    return {'potential_in': potential_in, 'potential_out': potential_out}


def calc_market_weight(rankings):
    """市值權重 Top 150"""
    top150 = [s.copy() for s in rankings[:150]] if rankings else []
    log(f"  Market Weight: {len(top150)} stocks")
    return {'stocks': top150}


# ── Main Entry ──

def run(data: dict, validation: dict) -> dict:
    """執行所有訊號計算"""
    start = time.time()
    warnings = []

    history = data.get('indices_history', {})
    rankings = data.get('rankings', [])
    holdings_0050 = data.get('holdings_0050', [])
    validator_warnings = validation.get('warnings', [])

    # Risk signals
    risk_signals = calc_risk_signals(history, validator_warnings)

    # 0050 strategy
    strategy_0050 = calc_0050_strategy(rankings, holdings_0050)

    # Market weight
    market_weight = calc_market_weight(rankings)

    # Enrich with quotes (candidates + top 150)
    from macro_data_agent import fetch_stock_quotes_batch, enrich_stocks_with_quotes

    candidate_codes = [s['code'] for s in strategy_0050['potential_in'] + strategy_0050['potential_out']]
    if candidate_codes:
        quotes = fetch_stock_quotes_batch(candidate_codes)
        strategy_0050['potential_in'] = enrich_stocks_with_quotes(strategy_0050['potential_in'], quotes)
        strategy_0050['potential_out'] = enrich_stocks_with_quotes(strategy_0050['potential_out'], quotes)

    if market_weight['stocks']:
        top150_codes = [s['code'] for s in market_weight['stocks']]
        all_quotes = {}
        for i in range(0, len(top150_codes), 30):
            chunk = top150_codes[i:i+30]
            chunk_quotes = fetch_stock_quotes_batch(chunk)
            all_quotes.update(chunk_quotes)
            if i + 30 < len(top150_codes):
                time.sleep(1)
        market_weight['stocks'] = enrich_stocks_with_quotes(market_weight['stocks'], all_quotes)

    duration = int((time.time() - start) * 1000)
    log(f"Done in {duration}ms")

    return {
        'status': 'OK',
        'duration_ms': duration,
        'risk_signals': risk_signals,
        'strategy_0050': strategy_0050,
        'market_weight_top150': market_weight,
        'warnings': warnings,
    }


if __name__ == "__main__":
    print("Signal agent requires data from data_agent. Run via strategy_engine.py.")
