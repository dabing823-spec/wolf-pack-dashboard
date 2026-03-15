#!/usr/bin/env python3
"""
Wolf Pack Agent Orchestrator
==============================
串接所有 Agent 的主控腳本。

流程：
  1. quality_agent      → 檢查資料品質
  2. signal_agent       → 信號分析 + 日報
  3. dashboard_agent    → 更新 Dashboard JSON
  4. alert_agent        → 異動通知 (LINE)
  5. ai_research_agent  → NotebookLM 雙視角分析 (沈萬鈞 × 巨人傑)

用法：
  python orchestrator.py              # 全部執行
  python orchestrator.py --quality    # 只跑品質檢查
  python orchestrator.py --signal     # 只跑信號分析
  python orchestrator.py --dashboard  # 只跑 Dashboard 更新
  python orchestrator.py --alert      # 只跑異動通知
  python orchestrator.py --ai         # 只跑 AI 研究分析
  python orchestrator.py --news       # 只跑新聞三層分析
  python orchestrator.py --no-alert   # 全部執行但跳過通知
  python orchestrator.py --no-ai      # 全部執行但跳過 AI 分析
  python orchestrator.py --no-news    # 全部執行但跳過新聞分析
  python orchestrator.py --git-push   # 執行完後自動 git commit & push
"""

import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import get_env_info, LOG_DIR, REPO_DIR, IS_WINDOWS, IS_MAC


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def log_to_file(msg):
    log_path = LOG_DIR / "orchestrator.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def run_pipeline(args):
    log("=" * 55)
    log("🐺 Wolf Pack Agent Pipeline")
    log(f"   {get_env_info()}")
    log("=" * 55)
    log_to_file("Pipeline 啟動")

    results = {}
    run_all = not (args.quality or args.signal or args.dashboard or args.alert or args.ai or args.news)

    # ── Step 1: 資料品質檢查 ──
    if run_all or args.quality:
        log("\n━━━ Step 1/6: 資料品質檢查 ━━━")
        try:
            from quality_agent import run as run_quality
            results["quality"] = run_quality()
            status = results["quality"]["status"]
            log(f"  結果: {status}")
            log_to_file(f"quality_agent: {status}")

            if status == "FAIL" and run_all:
                log("  ❌ 資料品質有嚴重問題，但繼續執行後續 Agent")
        except Exception as e:
            log(f"  ❌ quality_agent 異常: {e}")
            results["quality"] = {"status": "ERROR", "error": str(e)}
            log_to_file(f"quality_agent ERROR: {e}")

    # ── Step 2: 信號分析 ──
    signal_result = None
    if run_all or args.signal:
        log("\n━━━ Step 2/6: 信號分析 ━━━")
        try:
            from signal_agent import run as run_signal
            signal_result = run_signal()
            results["signal"] = {
                "status": signal_result["status"],
                "date": signal_result.get("date"),
                "summary": signal_result.get("summary"),
            }
            log(f"  結果: {signal_result['status']}")
            if signal_result.get("summary"):
                s = signal_result["summary"]
                log(f"  新進場={s['new']}, 出場={s['exited']}, 加碼={s['added']}, 減碼={s['reduced']}")
            log_to_file(f"signal_agent: {signal_result['status']} date={signal_result.get('date')}")
        except Exception as e:
            log(f"  ❌ signal_agent 異常: {e}")
            results["signal"] = {"status": "ERROR", "error": str(e)}
            log_to_file(f"signal_agent ERROR: {e}")

    # ── Step 3: Dashboard 更新 ──
    if run_all or args.dashboard:
        log("\n━━━ Step 3/6: Dashboard 更新 ━━━")
        try:
            from dashboard_agent import run as run_dashboard
            results["dashboard"] = run_dashboard()
            log(f"  結果: {results['dashboard']['status']}")
            log_to_file(f"dashboard_agent: {results['dashboard']['status']}")
        except Exception as e:
            log(f"  ❌ dashboard_agent 異常: {e}")
            results["dashboard"] = {"status": "ERROR", "error": str(e)}
            log_to_file(f"dashboard_agent ERROR: {e}")

    # ── Step 4: 異動通知 ──
    if (run_all and not args.no_alert) or args.alert:
        log("\n━━━ Step 4/6: 異動通知 ━━━")
        try:
            from alert_agent import run as run_alert
            results["alert"] = run_alert(signal_result)
            log(f"  結果: {results['alert']['status']}")
            n_alerts = results['alert'].get('n_alerts', 0)
            if n_alerts:
                log(f"  異動數: {n_alerts}, 已發送: {results['alert'].get('sent')}")
            log_to_file(f"alert_agent: {results['alert']['status']} alerts={n_alerts}")
        except Exception as e:
            log(f"  ❌ alert_agent 異常: {e}")
            results["alert"] = {"status": "ERROR", "error": str(e)}
            log_to_file(f"alert_agent ERROR: {e}")

    # ── Step 5: AI 研究分析 ──
    if (run_all and not args.no_ai) or args.ai:
        log("\n━━━ Step 5/6: AI 研究分析 (NotebookLM) ━━━")
        try:
            from ai_research_agent import run as run_ai_research
            import asyncio as _aio
            _aio.run(run_ai_research())
            results["ai_research"] = {"status": "OK"}
            log(f"  結果: OK")
            log_to_file("ai_research_agent: OK")
        except Exception as e:
            log(f"  ⚠️ ai_research_agent 異常: {e}")
            log(f"  （NotebookLM session 可能過期，執行 notebooklm login 重新登入）")
            results["ai_research"] = {"status": "WARN", "error": str(e)}
            log_to_file(f"ai_research_agent WARN: {e}")

    # ── Step 6: 新聞三層分析 ──
    if (run_all and not args.no_news) or args.news:
        log("\n━━━ Step 6/6: 新聞三層分析 ━━━")
        try:
            from news_analysis_agent import run as run_news
            import asyncio as _aio2
            _aio2.run(run_news())
            results["news_analysis"] = {"status": "OK"}
            log(f"  結果: OK")
            log_to_file("news_analysis_agent: OK")
        except Exception as e:
            log(f"  ⚠️ news_analysis_agent 異常: {e}")
            results["news_analysis"] = {"status": "WARN", "error": str(e)}
            log_to_file(f"news_analysis_agent WARN: {e}")

    # ── Git push ──
    if args.git_push:
        log("\n━━━ Git Commit & Push ━━━")
        git_push(results)

    # ── 總結 ──
    log("\n" + "=" * 55)
    log("📊 Pipeline 完成摘要")
    log("=" * 55)
    for agent, r in results.items():
        status = r.get("status", "?")
        icon = "✅" if status == "OK" else "⚠️" if status in ("WARN", "SKIP") else "❌"
        log(f"  {icon} {agent}: {status}")

    overall = "OK"
    if any(r.get("status") == "ERROR" for r in results.values()):
        overall = "ERROR"
    elif any(r.get("status") == "FAIL" for r in results.values()):
        overall = "FAIL"
    elif any(r.get("status") == "WARN" for r in results.values()):
        overall = "WARN"

    log(f"\n🐺 整體狀態: {overall}")
    log_to_file(f"Pipeline 完成: {overall}")

    return {"overall": overall, "results": results}


def git_push(results):
    """Git commit & push dashboard 資料"""
    try:
        # Check if there are changes
        check = subprocess.run(
            ["git", "diff", "--quiet", "data/"],
            capture_output=True, cwd=str(REPO_DIR)
        )
        if check.returncode == 0:
            # Also check for untracked files in data/
            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "data/"],
                capture_output=True, text=True, cwd=str(REPO_DIR)
            )
            if not untracked.stdout.strip():
                log("  ℹ️ 無資料變更，跳過 git push")
                return

        today = datetime.now().strftime("%Y-%m-%d")
        signal_date = ""
        if "signal" in results and results["signal"].get("date"):
            signal_date = results["signal"]["date"]

        # Stage
        subprocess.run(["git", "add", "data/", "scripts/agents/"], capture_output=True, cwd=str(REPO_DIR))

        # Commit
        msg = f"📊 Daily update: {signal_date or today}"
        commit = subprocess.run(
            ["git", "commit", "-m", msg],
            capture_output=True, text=True, cwd=str(REPO_DIR)
        )
        if commit.returncode == 0:
            log(f"  ✅ Git commit: {msg}")
        else:
            log(f"  ⚠️ Git commit: {commit.stderr.strip()}")
            return

        # Push
        push = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True, text=True, cwd=str(REPO_DIR)
        )
        if push.returncode == 0:
            log("  ✅ Git push 成功")
        else:
            log(f"  ❌ Git push 失敗: {push.stderr.strip()}")

    except Exception as e:
        log(f"  ❌ Git 異常: {e}")


def main():
    parser = argparse.ArgumentParser(description="🐺 Wolf Pack Agent Orchestrator")
    parser.add_argument("--quality", action="store_true", help="只跑品質檢查")
    parser.add_argument("--signal", action="store_true", help="只跑信號分析")
    parser.add_argument("--dashboard", action="store_true", help="只跑 Dashboard 更新")
    parser.add_argument("--alert", action="store_true", help="只跑異動通知")
    parser.add_argument("--ai", action="store_true", help="只跑 AI 研究分析")
    parser.add_argument("--no-alert", action="store_true", help="跳過通知")
    parser.add_argument("--news", action="store_true", help="只跑新聞三層分析")
    parser.add_argument("--no-ai", action="store_true", help="跳過 AI 分析")
    parser.add_argument("--no-news", action="store_true", help="跳過新聞分析")
    parser.add_argument("--git-push", action="store_true", help="完成後 git commit & push")
    args = parser.parse_args()

    result = run_pipeline(args)
    sys.exit(0 if result["overall"] in ("OK", "WARN") else 1)


if __name__ == "__main__":
    main()
