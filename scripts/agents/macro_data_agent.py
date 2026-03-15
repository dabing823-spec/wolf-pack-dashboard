#!/usr/bin/env python3
"""
Macro Data Agent — 宏觀資料抓取
================================
負責所有外部資料抓取：Yahoo Finance (9 symbols)、TAIFEX 市值排名、
MoneyDJ ETF 持股、個股報價。

標準介面：run() → {status, duration_ms, data, stats, warnings}
"""

import sys
import io
import re
import time
from pathlib import Path
from datetime import datetime

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_DIR

# ── Constants ──
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

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

TAIFEX_RANKING_URL = "https://www.taifex.com.tw/cht/9/futuresQADetail"
MONEYDJ_ETF_URL = "https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid={}.TW"
INDICES_HISTORY_PATH = DATA_DIR / "indices_history.json"


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] [DataAgent] {msg}")


def _load_json(path):
    import json
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_json(path, data):
    import json
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


# ── Fetch Functions ──

def fetch_indices_history():
    """抓取 9 個風險指標的 60 天歷史，合併到 indices_history.json"""
    import requests as _req

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }

    history = {}
    if INDICES_HISTORY_PATH.exists():
        try:
            loaded = _load_json(INDICES_HISTORY_PATH)
            if isinstance(loaded, dict):
                history = loaded
            else:
                log("  WARNING: indices_history.json has wrong format, regenerating")
        except Exception:
            pass

    log(f"Fetching indices history (3 months, {len(RISK_SYMBOLS)} symbols)...")

    for key, symbol in RISK_SYMBOLS.items():
        try:
            url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
                   f'?range=3mo&interval=1d')
            r = _req.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                log(f"  {key}: HTTP {r.status_code}")
                continue

            chart = r.json().get('chart', {}).get('result', [{}])[0]
            timestamps = chart.get('timestamp', [])
            closes = chart.get('indicators', {}).get('quote', [{}])[0].get('close', [])

            if not timestamps or not closes:
                continue

            new_records = {}
            for ts, c in zip(timestamps, closes):
                if c is not None:
                    dt = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
                    new_records[dt] = round(c, 4)

            existing = {r['date']: r['close'] for r in history.get(key, [])}
            existing.update(new_records)
            sorted_dates = sorted(existing.keys())[-90:]
            history[key] = [{'date': d, 'close': existing[d]} for d in sorted_dates]

            log(f"  {key}: {len(history[key])} days")
            time.sleep(0.3)

        except Exception as e:
            log(f"  {key} failed: {e}")

    # Fear & Greed from CNN
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
                log(f"  fear_greed: {len(history['fear_greed'])} days")
    except Exception as e:
        log(f"  fear_greed failed: {e}")

    _save_json(INDICES_HISTORY_PATH, history)
    return history


def fetch_taifex_rankings(limit=200):
    """從期交所抓取市值排名"""
    import requests
    log(f"Fetching TAIFEX rankings (top {limit})...")

    try:
        r = requests.get(TAIFEX_RANKING_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        encoding = r.apparent_encoding or 'big5'
        html_text = r.content.decode(encoding, errors='ignore')
    except Exception as e:
        log(f"  TAIFEX request failed: {e}")
        return []

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
            log(f"  {len(rows[:limit])} stocks parsed")
            return rows[:limit]
    except ImportError:
        pass

    # pandas fallback
    try:
        dfs = pd.read_html(io.StringIO(html_text))
        for df in dfs:
            cols = ''.join(str(c) for c in df.columns)
            if '排名' in cols and ('名稱' in cols or '代號' in cols):
                df.columns = [str(c).replace(' ', '') for c in df.columns]
                col_map = {}
                for c in df.columns:
                    if '排名' in c: col_map[c] = '排名'
                    elif '代' in c: col_map[c] = '股票代碼'
                    elif '名' in c: col_map[c] = '股票名稱'
                df = df.rename(columns=col_map)
                df = df[pd.to_numeric(df['排名'], errors='coerce').notnull()]
                df['排名'] = df['排名'].astype(int)
                df['股票代碼'] = df['股票代碼'].astype(str).str.extract(r'(\d{4})')[0]
                df = df.sort_values('排名').head(limit)
                rows = [{'rank': int(row['排名']), 'code': row['股票代碼'], 'name': row['股票名稱']}
                        for _, row in df.iterrows()]
                log(f"  {len(rows)} stocks (pandas)")
                return rows
    except Exception as e:
        log(f"  pandas fallback failed: {e}")

    return []


def fetch_etf_holdings(etf_code='0050', max_retries=3):
    """從 MoneyDJ 抓取 ETF 成分股名稱（含重試機制）"""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    url = MONEYDJ_ETF_URL.format(etf_code)
    log(f"Fetching {etf_code} holdings from MoneyDJ...")

    ua_list = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    ]

    for attempt in range(max_retries):
        try:
            hdrs = {
                'User-Agent': ua_list[attempt % len(ua_list)],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://www.moneydj.com/ETF/X/Basic/Basic0007.xdjhtm?etfid=0050.TW',
            }
            r = requests.get(url, headers=hdrs, timeout=15, verify=False)

            if r.status_code != 200:
                log(f"  Attempt {attempt+1}: HTTP {r.status_code}")
                time.sleep(1)
                continue

            if len(r.content) < 1000:
                log(f"  Attempt {attempt+1}: empty response ({len(r.content)} bytes)")
                time.sleep(2)
                continue

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

            if names:
                log(f"  {etf_code} holdings: {len(names)} stocks (attempt {attempt+1})")
                return names
            else:
                log(f"  Attempt {attempt+1}: parsed but no names found")
                time.sleep(1)

        except Exception as e:
            log(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(1)

    log(f"  All {max_retries} attempts failed for {etf_code}")
    return set()


def fetch_stock_quotes_batch(codes):
    """用 Yahoo Finance 批次抓取股價"""
    import requests as _req

    if not codes:
        return {}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }

    result = {}
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

            result[code] = {
                'price': price, 'prev_close': prev_close,
                'change': change, 'change_pct': change_pct,
                'volume': volume, 'turnover': turnover,
            }
            time.sleep(0.3)

        except Exception:
            pass

    return result


def enrich_stocks_with_quotes(stocks, quotes):
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


# ── Main Entry ──

def run() -> dict:
    """三個資料源同步抓取（ThreadPoolExecutor），回傳標準 agent result"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    start = time.time()
    warnings = []
    timings = {}

    indices_history = {}
    rankings = []
    holdings_0050 = set()

    # ── 三源同步抓取 ──
    log("Starting parallel fetch (Yahoo + TAIFEX + MoneyDJ)...")

    def _task_indices():
        t0 = time.time()
        result = fetch_indices_history()
        return 'indices', result, int((time.time() - t0) * 1000)

    def _task_taifex():
        t0 = time.time()
        result = fetch_taifex_rankings(limit=200)
        return 'taifex', result, int((time.time() - t0) * 1000)

    def _task_holdings():
        t0 = time.time()
        result = fetch_etf_holdings('0050')
        return 'holdings', result, int((time.time() - t0) * 1000)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(_task_indices),
            executor.submit(_task_taifex),
            executor.submit(_task_holdings),
        ]
        for future in as_completed(futures):
            try:
                name, result, dur = future.result()
                timings[name] = dur
                if name == 'indices':
                    indices_history = result
                elif name == 'taifex':
                    rankings = result
                elif name == 'holdings':
                    holdings_0050 = result
                log(f"  {name} done in {dur}ms")
            except Exception as e:
                log(f"  Task failed: {e}")

    # ── Validation ──
    if not rankings:
        warnings.append({'level': 'ERROR', 'symbol': 'taifex', 'msg': 'TAIFEX 排名抓取失敗'})
    if not holdings_0050:
        warnings.append({'level': 'WARN', 'symbol': '0050', 'msg': '0050 持股抓取失敗'})

    # ── Stats ──
    indices_count = sum(1 for k, v in indices_history.items() if v)
    min_days = min((len(v) for v in indices_history.values() if v), default=0)
    max_days = max((len(v) for v in indices_history.values() if v), default=0)
    total_datapoints = sum(len(v) for v in indices_history.values() if v)

    duration = int((time.time() - start) * 1000)
    status = 'ERROR' if any(w['level'] == 'ERROR' for w in warnings) else \
             'WARN' if warnings else 'OK'

    log(f"All done in {duration}ms (parallel) — status={status}")

    return {
        'status': status,
        'duration_ms': duration,
        'data': {
            'indices_history': indices_history,
            'rankings': rankings,
            'holdings_0050': list(holdings_0050),
        },
        'stats': {
            'indices_symbols': indices_count,
            'indices_min_days': min_days,
            'indices_max_days': max_days,
            'indices_total_datapoints': total_datapoints,
            'rankings_count': len(rankings),
            'holdings_0050_count': len(holdings_0050),
            'task_timings': timings,
        },
        'warnings': warnings,
    }


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != 'data'}, ensure_ascii=False, indent=2))
