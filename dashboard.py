"""Streamlit dashboard for crypto-agency — reads from committed audit.db."""
import streamlit as st
import sqlite3
import os
from pathlib import Path

# Load secrets on cloud (Streamlit Community Cloud)
try:
    if hasattr(st, "secrets") and len(st.secrets) > 0:
        for k, v in st.secrets.items():
            os.environ.setdefault(k, str(v))
except Exception:
    pass

st.set_page_config(page_title="Crypto Agency", layout="wide", page_icon="📊")

DB = "logs/audit.db"

st.title("📊 Crypto Agency Dashboard")
st.caption("Bitget Demo • BTC Trend-Following • EMA50/200 + ADX")

if not Path(DB).exists():
    st.warning("No database yet — signals will appear after the first GitHub Actions run.")
    st.stop()

import pandas as pd
from datetime import datetime, timedelta

# DB file last modified
mtime = datetime.fromtimestamp(Path(DB).stat().st_mtime)
st.caption(f"Last DB update: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

conn = sqlite3.connect(DB)

def safe_read(query, params=None):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame()

signals = safe_read("SELECT * FROM signals ORDER BY ts DESC")
decisions = safe_read("SELECT * FROM decisions ORDER BY ts DESC LIMIT 200")
orders = safe_read("SELECT * FROM orders ORDER BY ts DESC LIMIT 200")
conn.close()

# Metrics
closed = signals[signals["outcome"].isin(["win", "loss", "timeout"])] if len(signals) else pd.DataFrame()
total_trades = len(closed)
wins = (closed["outcome"] == "win").sum() if len(closed) else 0
losses = (closed["outcome"] == "loss").sum() if len(closed) else 0
win_rate = (wins / (wins + losses) * 100) if (wins + losses) else 0
total_pnl = closed["pnl_pct"].sum() if len(closed) and "pnl_pct" in closed else 0
open_count = (signals["outcome"] == "open").sum() if len(signals) else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Trades", int(total_trades))
col2.metric("Win Rate", f"{win_rate:.1f}%")
col3.metric("Open Positions", int(open_count))
col4.metric("Cumulative P&L", f"{total_pnl:+.2f}%")

st.divider()

st.subheader("📈 Signals Log")
if len(signals):
    cols = [c for c in ["ts","symbol","direction","confidence","agents_aligned",
                        "entry","stop_loss","take_profit","rr_ratio","outcome","pnl_pct"]
            if c in signals.columns]
    st.dataframe(signals[cols], use_container_width=True, hide_index=True)
else:
    st.info("No signals yet. System is waiting for a valid setup (golden cross + ADX ≥ 22).")

st.subheader("🎯 Recent Decisions")
if len(decisions):
    st.dataframe(decisions, use_container_width=True, hide_index=True)
else:
    st.info("No decisions yet.")

st.subheader("📤 Recent Orders")
if len(orders):
    cols = [c for c in ["ts","symbol","side","qty","entry","stop_loss","take_profit","status"]
            if c in orders.columns]
    st.dataframe(orders[cols], use_container_width=True, hide_index=True)
else:
    st.info("No orders yet.")

st.divider()
st.caption("Powered by GitHub Actions + Bitget Demo API")
