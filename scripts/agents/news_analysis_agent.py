#!/usr/bin/env python3
"""
News 3-Layer Analysis Agent — 巨人傑三層分析框架。

讀取 strategy.json 的風險訊號摘要，
透過 NotebookLM 生成三層分析（表面/隱藏/決策），
結果寫入 data/news_analysis.json 供前端顯示。

用法:
    python news_analysis_agent.py                        # 只跑 macro_analysis
    python news_analysis_agent.py --news "Fed 暫停升息"  # 分析一則新聞
    python news_analysis_agent.py --dry-run              # 顯示問題但不執行
    python news_analysis_agent.py --force                # 強制重跑（忽略當日快取）
"""

import argparse
import asyncio
import json
import re
import sys
import io
import platform
from datetime import datetime
from pathlib import Path

if platform.system() == "Windows":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news_analysis.json"

NOTEBOOK_NAME = "巨人思維"
MAX_NEWS_KEEP = 30


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] 📰 {msg}", file=sys.stderr)


def load_existing() -> dict:
    """Load existing news_analysis.json."""
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": 1,
        "updated_at": "",
        "notebook": NOTEBOOK_NAME,
        "news_analyses": [],
        "macro_analysis": None,
    }


def load_risk_summary() -> str:
    """Build a risk signals summary from strategy.json."""
    strat_path = DATA_DIR / "strategy.json"
    if not strat_path.exists():
        return ""

    with open(strat_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rs = data.get("risk_signals")
    if not rs:
        return ""

    parts = [f"風險評分: {rs.get('score', '-')}/10 ({rs.get('level', '-')})"]
    parts.append(f"紅燈 {rs.get('n_red', 0)} 黃燈 {rs.get('n_yellow', 0)} 綠燈 {rs.get('n_green', 0)}")

    for s in rs.get("signals", []):
        signal = s.get("signal", "-")
        name = s.get("name", s.get("key", "?"))
        value = s.get("value", "-")
        slope = s.get("slope_20d", "-")
        parts.append(f"  {name}: {signal} (值={value}, 斜率={slope})")

    return "\n".join(parts)


def build_macro_question(risk_summary: str) -> str:
    """Build the macro analysis question for NotebookLM."""
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"今天是 {today}。以下是當前宏觀風險訊號摘要：\n\n"
        f"{risk_summary}\n\n"
        f"請用巨人傑的三層分析框架解讀當前宏觀環境。\n"
        f"請嚴格以 JSON 格式回答（不要有其他文字），格式如下：\n"
        f'{{\n'
        f'  "layer1": {{"event": "本週宏觀環境綜合解讀", "data": "各指標數據摘要", "market_reaction": "全球市場反應", "timeline": "數據截止時間"}},\n'
        f'  "layer2": {{"beneficiaries": ["受益族群1", "受益族群2"], "victims": ["受害族群1"], "pricing_status": "市場定價程度", "real_motive": "真實動機分析", "market_blind_spots": "市場盲點"}},\n'
        f'  "layer3": {{"position_impact": "對部位的影響", "expected_value": "期望值分析", "timing": "時機建議", "risk_assessment": "風險評估", "action_plan": "具體行動方案"}}\n'
        f'}}'
    )


def build_news_question(headline: str) -> str:
    """Build a news analysis question for NotebookLM."""
    return (
        f"以下這則新聞：\n\n「{headline}」\n\n"
        f"請用巨人傑的三層分析框架解構這則新聞。\n"
        f"請嚴格以 JSON 格式回答（不要有其他文字），格式如下：\n"
        f'{{\n'
        f'  "layer1": {{"event": "一句話描述事件", "data": "關鍵數據", "market_reaction": "市場初反應", "timeline": "時間狀態"}},\n'
        f'  "layer2": {{"beneficiaries": ["受益者1", "受益者2"], "victims": ["受害者1"], "pricing_status": "定價程度", "real_motive": "真實動機", "market_blind_spots": "市場盲點"}},\n'
        f'  "layer3": {{"position_impact": "部位影響", "expected_value": "期望值", "timing": "時機建議", "risk_assessment": "風險評估", "action_plan": "行動方案"}}\n'
        f'}}'
    )


def parse_layer_response(raw: str) -> dict:
    """Parse AI response into structured layer data."""
    # 1. Try direct JSON parse
    try:
        data = json.loads(raw)
        if "layer1" in data:
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Try extracting ```json ... ``` block
    m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', raw)
    if m:
        try:
            data = json.loads(m.group(1))
            if "layer1" in data:
                return data
        except json.JSONDecodeError:
            pass

    # 3. Try finding first { to last }
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start:end + 1])
            if "layer1" in data:
                return data
        except json.JSONDecodeError:
            pass

    # 4. Fallback: put raw text into layer1.event
    log("  JSON 解析失敗，使用 fallback 模式")
    return {
        "layer1": {"event": raw[:500], "data": "-", "market_reaction": "-", "timeline": "-"},
        "layer2": {"beneficiaries": [], "victims": [], "pricing_status": "-", "real_motive": "-", "market_blind_spots": "-"},
        "layer3": {"position_impact": "-", "expected_value": "-", "timing": "-", "risk_assessment": "-", "action_plan": "-"},
    }


def guess_category(headline: str) -> tuple[str, str]:
    """Guess news category and color from headline."""
    h = headline.lower()
    if any(k in h for k in ["fed", "fomc", "央行", "利率", "升息", "降息", "boj", "ecb"]):
        return "央行政策", "orange"
    if any(k in h for k in ["cpi", "非農", "gdp", "pmi", "就業", "通膨", "失業"]):
        return "經濟數據", "blue"
    if any(k in h for k in ["財報", "eps", "營收", "毛利", "展望", "法說"]):
        return "財報發布", "purple"
    if any(k in h for k in ["戰爭", "制裁", "關稅", "地緣", "台海", "中國", "俄", "烏"]):
        return "地緣政治", "red"
    if any(k in h for k in ["etf", "持股", "經理人", "基金"]):
        return "ETF 動態", "green"
    return "市場動態", "blue"


async def ask_notebook(client, question: str) -> str:
    """Ask a question against the NotebookLM notebook."""
    notebooks = await client.notebooks.list()
    nb = None
    for n in notebooks:
        if NOTEBOOK_NAME.lower() in n.title.lower():
            nb = n
            break

    if not nb:
        return f"（找不到筆記本：{NOTEBOOK_NAME}）"

    try:
        result = await client.chat.ask(nb.id, question=question)
        return result.answer
    except Exception as e:
        return f"（查詢失敗：{e}）"


async def run(news_headlines: list[str] | None = None, dry_run: bool = False, force: bool = False):
    existing = load_existing()
    today = datetime.now().strftime("%Y-%m-%d")

    risk_summary = load_risk_summary()
    if not risk_summary and not news_headlines:
        log("沒有風險數據也沒有新聞標題，跳過")
        return

    # Check if macro already done today
    skip_macro = False
    if not force and existing.get("macro_analysis"):
        if existing["macro_analysis"].get("date") == today:
            log(f"今日 ({today}) macro_analysis 已存在，跳過（用 --force 覆蓋）")
            skip_macro = True

    if dry_run:
        if risk_summary and not skip_macro:
            log("Macro question:")
            log(build_macro_question(risk_summary)[:200] + "...")
        if news_headlines:
            for h in news_headlines:
                log(f"News question: {h[:100]}...")
        return

    from notebooklm import NotebookLMClient

    async with await NotebookLMClient.from_storage() as client:
        # Macro analysis
        if risk_summary and not skip_macro:
            log("分析宏觀風險環境...")
            question = build_macro_question(risk_summary)
            raw = await ask_notebook(client, question)
            log(f"  收到回應（{len(raw)} 字）")
            layers = parse_layer_response(raw)
            existing["macro_analysis"] = {
                "date": today,
                "risk_context": risk_summary.split("\n")[0],
                **layers,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

        # News analyses
        if news_headlines:
            for headline in news_headlines:
                log(f"分析新聞: {headline[:60]}...")
                question = build_news_question(headline)
                raw = await ask_notebook(client, question)
                log(f"  收到回應（{len(raw)} 字）")
                layers = parse_layer_response(raw)
                category, cat_color = guess_category(headline)
                news_id = today.replace("-", "") + f"_{len(existing['news_analyses']) + 1:03d}"
                entry = {
                    "id": news_id,
                    "date": today,
                    "headline": headline,
                    "category": category,
                    "category_color": cat_color,
                    **layers,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                existing["news_analyses"].insert(0, entry)

            # Keep only latest N
            existing["news_analyses"] = existing["news_analyses"][:MAX_NEWS_KEEP]

        # Save
        existing["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        existing["notebook"] = NOTEBOOK_NAME

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        log(f"結果已寫入 {OUTPUT_FILE}")


def main():
    parser = argparse.ArgumentParser(description="News 3-Layer Analysis Agent")
    parser.add_argument("--news", nargs="+", help="新聞標題（可多則）")
    parser.add_argument("--dry-run", action="store_true", help="顯示問題但不執行")
    parser.add_argument("--force", action="store_true", help="強制重跑（忽略當日快取）")
    args = parser.parse_args()

    asyncio.run(run(news_headlines=args.news, dry_run=args.dry_run, force=args.force))


if __name__ == "__main__":
    main()
