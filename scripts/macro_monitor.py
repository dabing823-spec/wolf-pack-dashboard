#!/usr/bin/env python3
"""
Global Macro Monitor — 總經指標即時監控
========================================
輕量級腳本，只抓五大總經指標 + VIX + Fear & Greed，
不需要 Excel/Google Drive，可獨立快速執行。

用途：
  1. 盤前簡報 (08:30 TW) — 美股收盤後的最新數據
  2. 盤後快速更新 (13:35 TW) — 台股收盤後立即更新指標
  3. 盤中警報 — 指標突破門檻時發送 LINE 通知

用法：
  python macro_monitor.py                    # 更新指標到 strategy.json
  python macro_monitor.py --alert            # 更新 + 檢查門檻警報
  python macro_monitor.py --brief            # 產出盤前簡報文字
  python macro_monitor.py --brief --alert    # 簡報 + 警報
"""

import json
import os
import sys
import argparse
import requests
import re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
ALERT_STATE_PATH = DATA_DIR / ".macro_alert_state.json"
INDICES_HISTORY_PATH = DATA_DIR / "indices_history.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
}

# ── Phase 2: 警報門檻 ──
ALERT_THRESHOLDS = {
    'vix': {
        'high': 30, 'low': 15,
        'high_msg': '⚠️ VIX 突破 30 — 市場恐慌升溫',
        'low_msg': '💤 VIX 跌破 15 — 市場過度樂觀，留意反轉',
    },
    'dxy': {
        'daily_pct': 1.0,
        'up_msg': '💵 美元指數單日漲幅 > 1% — 全球流動性收縮風險',
        'down_msg': '💵 美元指數單日跌幅 > 1% — 資金外流，風險資產受惠',
    },
    'gold': {
        'daily_pct': 2.0,
        'up_msg': '🥇 黃金單日漲幅 > 2% — 避險需求急升',
        'down_msg': '🥇 黃金單日跌幅 > 2% — 避險情緒降溫',
    },
    'oil': {
        'daily_pct': 3.0,
        'up_msg': '🛢️ 原油單日漲幅 > 3% — 通膨壓力 / 供給衝擊',
        'down_msg': '🛢️ 原油單日跌幅 > 3% — 需求擔憂 / 衰退風險',
    },
    'us10y': {
        'daily_bps': 10,
        'up_msg': '📈 10Y殖利率單日升 > 10bps — 利率快速上行，壓制股市',
        'down_msg': '📈 10Y殖利率單日降 > 10bps — 降息預期增強，利多股市',
    },
}


def fetch_yahoo(symbol):
    """Fetch price + prev close from Yahoo Finance."""
    try:
        r = requests.get(
            f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d',
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            res = r.json().get('chart', {}).get('result', [{}])[0]
            closes = [c for c in res.get('indicators', {}).get('quote', [{}])[0].get('close', []) if c is not None]
            if len(closes) >= 2:
                return round(closes[-1], 4), round(closes[-2], 4)
            elif closes:
                return round(closes[-1], 4), None
    except Exception as e:
        print(f"  [WARN] Yahoo {symbol}: {e}")
    return None, None


def fetch_all_indices():
    """Fetch all macro indices."""
    symbols = {
        'vix':   '%5EVIX',
        'dxy':   'DX-Y.NYB',
        'oil':   'CL%3DF',
        'gold':  'GC%3DF',
        'us10y': '%5ETNX',
    }

    result = {}
    for key, sym in symbols.items():
        price, prev = fetch_yahoo(sym)
        if price is not None:
            result[key] = price
            if prev is not None:
                chg = round(price - prev, 4)
                chg_pct = round(chg / prev * 100, 2) if prev else 0
                result[f'{key}_prev'] = prev
                result[f'{key}_chg'] = chg
                result[f'{key}_chg_pct'] = chg_pct
            print(f"  {key}: {price}" + (f" ({chg:+.2f}, {chg_pct:+.2f}%)" if prev else ""))

    # CNN Fear & Greed
    try:
        r = requests.get(
            'https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
            headers={**HEADERS, 'Referer': 'https://edition.cnn.com/markets/fear-and-greed'},
            timeout=10
        )
        if r.status_code == 200:
            fg = r.json().get('fear_and_greed', {})
            if fg.get('score') is not None:
                result['fear_greed'] = round(fg['score'], 1)
                result['fear_greed_rating'] = fg.get('rating', '')
                prev_fg = fg.get('previous_close')
                if prev_fg is not None:
                    result['fear_greed_prev'] = round(prev_fg, 1)
                    result['fear_greed_chg'] = round(result['fear_greed'] - prev_fg, 1)
                print(f"  fear_greed: {result['fear_greed']} ({result['fear_greed_rating']})")
    except Exception as e:
        print(f"  [WARN] Fear & Greed: {e}")

    result['updated_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    return result


def update_strategy_json(indices):
    """Update market_indices in strategy.json."""
    strategy_path = DATA_DIR / "strategy.json"
    if strategy_path.exists():
        with open(strategy_path, 'r', encoding='utf-8') as f:
            strategy = json.load(f)
    else:
        strategy = {}

    strategy['market_indices'] = indices
    with open(strategy_path, 'w', encoding='utf-8') as f:
        json.dump(strategy, f, ensure_ascii=False)
    print(f"  strategy.json updated ({strategy_path.stat().st_size:,} bytes)")


def save_history(indices):
    """Append to indices_history.json for trend tracking."""
    history = []
    if INDICES_HISTORY_PATH.exists():
        try:
            with open(INDICES_HISTORY_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                history = data if isinstance(data, list) else []
        except Exception:
            pass

    entry = {
        'timestamp': indices.get('updated_at', ''),
        'vix': indices.get('vix'),
        'dxy': indices.get('dxy'),
        'oil': indices.get('oil'),
        'gold': indices.get('gold'),
        'us10y': indices.get('us10y'),
        'fear_greed': indices.get('fear_greed'),
    }
    history.append(entry)

    # Keep last 200 entries
    history = history[-200:]
    with open(INDICES_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False)


def check_alerts(indices):
    """Phase 2: Check thresholds and return alert messages."""
    alerts = []

    # VIX level alerts
    vix = indices.get('vix')
    if vix is not None:
        t = ALERT_THRESHOLDS['vix']
        if vix >= t['high']:
            alerts.append(f"{t['high_msg']} (VIX={vix})")
        elif vix <= t['low']:
            alerts.append(f"{t['low_msg']} (VIX={vix})")

    # Percentage-based alerts (DXY, Gold, Oil)
    for key in ['dxy', 'gold', 'oil']:
        chg_pct = indices.get(f'{key}_chg_pct')
        if chg_pct is not None:
            t = ALERT_THRESHOLDS[key]
            threshold = t['daily_pct']
            if chg_pct >= threshold:
                alerts.append(f"{t['up_msg']} ({chg_pct:+.2f}%)")
            elif chg_pct <= -threshold:
                alerts.append(f"{t['down_msg']} ({chg_pct:+.2f}%)")

    # US 10Y basis points
    us10y_chg = indices.get('us10y_chg')
    if us10y_chg is not None:
        bps = abs(us10y_chg * 100)
        t = ALERT_THRESHOLDS['us10y']
        if bps >= t['daily_bps']:
            if us10y_chg > 0:
                alerts.append(f"{t['up_msg']} ({bps:.0f}bps)")
            else:
                alerts.append(f"{t['down_msg']} ({bps:.0f}bps)")

    return alerts


def should_send_alert(alerts):
    """Avoid duplicate alerts within 6 hours."""
    state = {}
    if ALERT_STATE_PATH.exists():
        try:
            with open(ALERT_STATE_PATH, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception:
            pass

    now = datetime.utcnow().isoformat()
    last_sent = state.get('last_sent', '')
    if last_sent:
        try:
            last_dt = datetime.fromisoformat(last_sent)
            hours_diff = (datetime.utcnow() - last_dt).total_seconds() / 3600
            if hours_diff < 6:
                # Check if same alerts
                if state.get('last_alerts') == [a[:30] for a in alerts]:
                    return False
        except Exception:
            pass

    # Save state
    state['last_sent'] = now
    state['last_alerts'] = [a[:30] for a in alerts]
    with open(ALERT_STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False)
    return True


def send_line_alert(message):
    """Send LINE notification."""
    token = os.environ.get('LINE_NOTIFY_TOKEN', '')
    if not token:
        print("  LINE_NOTIFY_TOKEN not set, skipping")
        return False

    try:
        r = requests.post(
            'https://notify-api.line.me/api/notify',
            headers={'Authorization': f'Bearer {token}'},
            data={'message': message[:990]},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        print(f"  LINE send failed: {e}")
        return False


def generate_brief(indices):
    """Generate pre-market brief text."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    def fmt_chg(key):
        chg = indices.get(f'{key}_chg')
        pct = indices.get(f'{key}_chg_pct')
        if chg is not None:
            return f"{chg:+.2f} ({pct:+.2f}%)"
        return ""

    vix = indices.get('vix', '-')
    vix_level = '恐慌' if vix != '-' and vix >= 30 else '偏高' if vix != '-' and vix >= 20 else '正常' if vix != '-' and vix >= 15 else '低波動'

    fg = indices.get('fear_greed', '-')
    fg_map = {'extreme fear': '極度恐懼', 'fear': '恐懼', 'neutral': '中性', 'greed': '貪婪', 'extreme greed': '極度貪婪'}
    fg_rating = fg_map.get(indices.get('fear_greed_rating', '').lower(), indices.get('fear_greed_rating', ''))

    # Sync signal
    up = sum(1 for k in ['dxy', 'oil', 'gold', 'us10y'] if (indices.get(f'{k}_chg_pct') or 0) > 0.1)
    down = sum(1 for k in ['dxy', 'oil', 'gold', 'us10y'] if (indices.get(f'{k}_chg_pct') or 0) < -0.1)
    sync = ""
    if up >= 3:
        sync = f"\n  ⚠️ {up}/4 指標同步上漲 — 留意通膨壓力"
    elif down >= 3:
        sync = f"\n  📉 {down}/4 指標同步下跌 — 留意經濟降溫"

    brief = f"""
🐺 JOY88 市場簡報 | {now}
━━━━━━━━━━━━━━━━━━
▎情緒
  ⚡ VIX: {vix} ({vix_level})
  🎭 F&G: {fg} ({fg_rating})

▎五大指標
  💵 DXY:  {indices.get('dxy', '-')}  {fmt_chg('dxy')}
  🛢️ Oil:  {indices.get('oil', '-')}  {fmt_chg('oil')}
  🥇 Gold: {indices.get('gold', '-')}  {fmt_chg('gold')}
  📈 10Y:  {indices.get('us10y', '-')}  {fmt_chg('us10y')}{sync}
━━━━━━━━━━━━━━━━━━"""

    return brief.strip()


def main():
    parser = argparse.ArgumentParser(description='Global Macro Monitor')
    parser.add_argument('--alert', action='store_true', help='Check alert thresholds')
    parser.add_argument('--brief', action='store_true', help='Generate market brief')
    parser.add_argument('--line', action='store_true', help='Send brief/alerts via LINE')
    args = parser.parse_args()

    print("🐺 Macro Monitor — Fetching indices...")
    indices = fetch_all_indices()

    if not indices.get('vix'):
        print("❌ Failed to fetch any data")
        sys.exit(1)

    # Always update strategy.json and history
    update_strategy_json(indices)
    save_history(indices)

    # Brief
    if args.brief:
        brief = generate_brief(indices)
        print(brief)
        if args.line:
            send_line_alert(brief)
            print("  LINE brief sent")

    # Alerts
    if args.alert:
        alerts = check_alerts(indices)
        if alerts:
            print(f"\n🚨 {len(alerts)} alert(s) triggered:")
            for a in alerts:
                print(f"  {a}")

            if args.line and should_send_alert(alerts):
                msg = "\n🚨 JOY88 總經警報\n" + "\n".join(alerts)
                send_line_alert(msg)
                print("  LINE alert sent")
        else:
            print("\n✅ No alerts triggered")

    print("\nDone.")


if __name__ == '__main__':
    main()
