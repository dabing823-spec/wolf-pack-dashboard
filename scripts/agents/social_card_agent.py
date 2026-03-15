#!/usr/bin/env python3
"""
Social Card Agent — 每日風險訊號社群圖卡產生器
================================================
讀取 strategy.json，產生 PNG 圖卡供 FB/IG 分享。

用法：
  python social_card_agent.py                 # 產生圖卡到 data/
  python social_card_agent.py --preview       # 產生後自動開啟
  python social_card_agent.py --output path   # 指定輸出路徑

輸出：
  data/daily_card_{date}.png (1080x1350, IG 最佳比例 4:5)
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_DIR

STRATEGY_PATH = DATA_DIR / "strategy.json"
CARD_WIDTH = 1080
CARD_HEIGHT = 1350


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] [SocialCard] {msg}")


def load_strategy():
    with open(STRATEGY_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def draw_rounded_rect(draw, xy, radius, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    r = radius
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
    draw.pieslice([x0, y0, x0 + 2*r, y0 + 2*r], 180, 270, fill=fill)
    draw.pieslice([x1 - 2*r, y0, x1, y0 + 2*r], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2*r, x0 + 2*r, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2*r, y1 - 2*r, x1, y1], 0, 90, fill=fill)


def generate_card(data, output_path):
    """產生社群圖卡 PNG"""
    from PIL import Image, ImageDraw, ImageFont

    rs = data.get('risk_signals', {})
    s0050 = data.get('strategy_0050', {})
    report_date = data.get('report_date', datetime.now().strftime('%Y-%m-%d'))
    score = rs.get('score', 0)
    level = rs.get('level', 'unknown')
    signals = rs.get('signals', [])

    # Colors
    BG = '#0f1117'
    CARD_BG = '#1a1d28'
    BORDER = '#2a2e3d'
    TEXT = '#e4e6eb'
    TEXT_MUTED = '#8b8fa3'
    ACCENT = '#4f8ef7'
    GREEN = '#00c48c'
    RED = '#ff4757'
    ORANGE = '#ffa502'
    CYAN = '#22d3ee'

    score_color = RED if score >= 7 else ORANGE if score >= 4 else GREEN
    level_map = {'high': '高度警戒', 'medium': '中度警戒', 'low': '風險偏低'}
    level_text = level_map.get(level, level)

    # Create image
    img = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # Try to load fonts (fallback to default)
    try:
        font_path_bold = "C:/Windows/Fonts/msjhbd.ttc"  # Microsoft JhengHei Bold
        font_path = "C:/Windows/Fonts/msjh.ttc"          # Microsoft JhengHei
        title_font = ImageFont.truetype(font_path_bold, 42)
        subtitle_font = ImageFont.truetype(font_path, 24)
        score_font = ImageFont.truetype(font_path_bold, 96)
        level_font = ImageFont.truetype(font_path_bold, 32)
        signal_font = ImageFont.truetype(font_path_bold, 22)
        signal_desc_font = ImageFont.truetype(font_path, 18)
        small_font = ImageFont.truetype(font_path, 16)
        footer_font = ImageFont.truetype(font_path, 14)
    except Exception:
        log("System fonts not found, using defaults")
        title_font = ImageFont.load_default()
        subtitle_font = title_font
        score_font = title_font
        level_font = title_font
        signal_font = title_font
        signal_desc_font = title_font
        small_font = title_font
        footer_font = title_font

    y = 40

    # ── Header ──
    draw.text((60, y), "JOY88", fill=ACCENT, font=title_font)
    draw.text((230, y + 8), "Risk Signal Daily", fill=TEXT_MUTED, font=subtitle_font)
    y += 60
    draw.text((60, y), report_date, fill=TEXT_MUTED, font=subtitle_font)
    y += 50

    # ── Divider ──
    draw.line([(60, y), (CARD_WIDTH - 60, y)], fill=BORDER, width=1)
    y += 30

    # ── Score Section ──
    # Circle
    cx, cy = CARD_WIDTH // 2, y + 90
    r = 80
    # Outer ring
    for angle_offset in range(360):
        import math
        angle = math.radians(angle_offset - 90)
        if angle_offset <= score / 10 * 360:
            color = score_color
        else:
            color = BORDER
        x1 = cx + (r - 3) * math.cos(angle)
        y1 = cy + (r - 3) * math.sin(angle)
        x2 = cx + (r + 3) * math.cos(angle)
        y2 = cy + (r + 3) * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=3)

    # Score text
    score_text = f"{score:.1f}"
    bbox = draw.textbbox((0, 0), score_text, font=score_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 10), score_text, fill=score_color, font=score_font)

    # /10 label
    bbox2 = draw.textbbox((0, 0), "/10", font=small_font)
    draw.text((cx - (bbox2[2] - bbox2[0]) // 2, cy + 45), "/10", fill=TEXT_MUTED, font=small_font)

    y = cy + 100

    # Level text
    bbox_l = draw.textbbox((0, 0), level_text, font=level_font)
    draw.text((cx - (bbox_l[2] - bbox_l[0]) // 2, y), level_text, fill=score_color, font=level_font)
    y += 50

    # Red/Yellow/Green counts
    n_red = rs.get('n_red', 0)
    n_yellow = rs.get('n_yellow', 0)
    n_green = rs.get('n_green', 0)
    counts_text = f"Red {n_red}  |  Yellow {n_yellow}  |  Green {n_green}"
    bbox_c = draw.textbbox((0, 0), counts_text, font=small_font)
    draw.text((cx - (bbox_c[2] - bbox_c[0]) // 2, y), counts_text, fill=TEXT_MUTED, font=small_font)
    y += 50

    # ── Divider ──
    draw.line([(60, y), (CARD_WIDTH - 60, y)], fill=BORDER, width=1)
    y += 25

    # ── Signal List ──
    for s in signals:
        sig_color = RED if s['signal'] == 'red' else ORANGE if s['signal'] == 'yellow' else GREEN
        icon = '▲' if s['signal'] == 'red' else '—' if s['signal'] == 'yellow' else '▼'

        # Phase badge
        phase = s.get('phase', 'stable')
        phase_text = '加速' if phase == 'accelerating' else '趨緩' if phase == 'decelerating' else '持平'
        phase_color = RED if phase == 'accelerating' else GREEN if phase == 'decelerating' else TEXT_MUTED

        # Draw signal card background
        draw_rounded_rect(draw, (60, y, CARD_WIDTH - 60, y + 72), 10, CARD_BG)

        # Icon
        draw.text((80, y + 12), icon, fill=sig_color, font=signal_font)

        # Name
        draw.text((120, y + 12), s['name'], fill=TEXT, font=signal_font)

        # Phase badge
        draw.text((340, y + 14), phase_text, fill=phase_color, font=signal_desc_font)

        # Value
        val = s.get('value')
        if val is not None:
            val_text = f"{val:.2f}" if isinstance(val, float) else str(val)
            bbox_v = draw.textbbox((0, 0), val_text, font=signal_font)
            draw.text((CARD_WIDTH - 80 - (bbox_v[2] - bbox_v[0]), y + 12), val_text, fill=sig_color, font=signal_font)

        # Desc
        desc = s.get('desc', '')
        if len(desc) > 40:
            desc = desc[:40] + '...'
        draw.text((120, y + 44), desc, fill=TEXT_MUTED, font=signal_desc_font)

        y += 82

    y += 10

    # ── 0050 Section ──
    pot_in = s0050.get('potential_in', [])
    pot_out = s0050.get('potential_out', [])
    if pot_in or pot_out:
        draw.line([(60, y), (CARD_WIDTH - 60, y)], fill=BORDER, width=1)
        y += 20
        draw.text((60, y), "0050 Strategy", fill=ACCENT, font=signal_font)
        y += 35

        if pot_in:
            names = ', '.join(f"{s['name']}(#{s['rank']})" for s in pot_in[:4])
            draw.text((80, y), f"▲ In:  {names}", fill=GREEN, font=signal_desc_font)
            y += 28
        if pot_out:
            names = ', '.join(f"{s['name']}(#{s['rank']})" for s in pot_out[:4])
            draw.text((80, y), f"▼ Out: {names}", fill=RED, font=signal_desc_font)
            y += 28

    # ── Footer ──
    y = CARD_HEIGHT - 60
    draw.line([(60, y - 15), (CARD_WIDTH - 60, y - 15)], fill=BORDER, width=1)
    draw.text((60, y), "dabing823-spec.github.io/joy88-etf-dashboard", fill=TEXT_MUTED, font=footer_font)
    draw.text((CARD_WIDTH - 260, y), "Not investment advice.", fill=TEXT_MUTED, font=footer_font)

    # Save
    img.save(output_path, 'PNG', quality=95)
    log(f"Card saved: {output_path} ({CARD_WIDTH}x{CARD_HEIGHT})")
    return output_path


def run(output_path=None, preview=False) -> dict:
    """執行社群圖卡產生"""
    start = time.time()

    if not STRATEGY_PATH.exists():
        log("strategy.json not found")
        return {'status': 'ERROR', 'error': 'strategy.json not found'}

    data = load_strategy()
    report_date = data.get('report_date', datetime.now().strftime('%Y-%m-%d'))

    if output_path is None:
        output_path = str(DATA_DIR / f"daily_card_{report_date}.png")

    log(f"Generating card for {report_date}...")
    card_path = generate_card(data, output_path)

    if preview:
        import subprocess
        subprocess.Popen(['start', '', card_path], shell=True)

    duration = int((time.time() - start) * 1000)
    return {
        'status': 'OK',
        'duration_ms': duration,
        'output': card_path,
        'date': report_date,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JOY88 Social Card Generator")
    parser.add_argument("--output", type=str, help="Output path")
    parser.add_argument("--preview", action="store_true", help="Open after generating")
    args = parser.parse_args()

    result = run(output_path=args.output, preview=args.preview)
    print(json.dumps(result, ensure_ascii=False, indent=2))
