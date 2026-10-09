"""Daily Telegram journal at 8am."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from datetime import datetime, timedelta, date
from config import AUDIT_DB

JOURNAL_MARKER = Path("logs/.last_journal")


def should_send_today():
    today = date.today().isoformat()
    if JOURNAL_MARKER.exists():
        return JOURNAL_MARKER.read_text().strip() != today
    return True


def mark_sent():
    JOURNAL_MARKER.parent.mkdir(exist_ok=True)
    JOURNAL_MARKER.write_text(date.today().isoformat())


def build_summary():
    try:
        import pandas as pd
    except ImportError:
        return "📅 Daily Journal — pandas not installed"

    conn = sqlite3.connect(AUDIT_DB)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    try:
        sigs = pd.read_sql(
            "SELECT * FROM signals WHERE ts LIKE ? OR ts LIKE ?",
            conn, params=(f"{yesterday}%", f"{today}%")
        )
        open_sigs = pd.read_sql(
            "SELECT * FROM signals WHERE outcome='open'", conn
        )
        closed = pd.read_sql(
            "SELECT * FROM signals WHERE outcome IN ('win','loss','timeout') AND ts >= ?",
            conn, params=((date.today() - timedelta(days=7)).isoformat(),)
        )
    except Exception as e:
        conn.close()
        return f"📅 Daily Journal — {today}\n(DB error: {e})"

    conn.close()

    lines = [f"📅 *Daily Journal — {today}*", ""]
    lines.append(f"*Last 24h:*")
    lines.append(f"  Signals: {len(sigs)}")
    lines.append(f"  Open positions: {len(open_sigs)}")
    lines.append("")
    lines.append(f"*Last 7 days:*")

    if len(closed):
        wins = (closed["outcome"] == "win").sum()
        losses = (closed["outcome"] == "loss").sum()
        pnl = closed["pnl_pct"].sum() if "pnl_pct" in closed else 0
        wr = wins / (wins + losses) * 100 if (wins + losses) else 0
        lines.append(f"  Closed: {len(closed)} ({wins}W / {losses}L)")
        lines.append(f"  Win rate: {wr:.1f}%")
        lines.append(f"  Cumul P&L: {pnl:+.2f}%")
    else:
        lines.append("  No closed trades.")

    if len(open_sigs):
        lines.append("")
        lines.append("*Open positions:*")
        for _, s in open_sigs.iterrows():
            lines.append(f"  {s['symbol']} {s['direction']} @ ${s['entry']:.2f}")

    return "\n".join(lines)


if __name__ == "__main__":
    from agents.reporter import ReporterAgent
    reporter = ReporterAgent()
    summary = build_summary()
    print(summary)
    print()
    if should_send_today():
        reporter._send(summary)
        mark_sent()
        print("✅ Journal sent to Telegram.")
    else:
        print("Already sent today. Skipping.")
