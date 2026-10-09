import sqlite3
import os
import json
from datetime import datetime, date
from config import AUDIT_DB, LOG_DIR


def ensure_schema(db_path):
    """Create all tables if they don't exist. Callable from anywhere."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL, symbol TEXT NOT NULL,
                decision TEXT NOT NULL, confidence INTEGER,
                ta_bias TEXT, sentiment_bias TEXT,
                risk_approved INTEGER, risk_reason TEXT, price REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL, symbol TEXT NOT NULL,
                side TEXT NOT NULL, qty REAL, entry REAL,
                stop_loss REAL, take_profit REAL,
                order_id TEXT, status TEXT, raw_response TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_pnl (
                day TEXT PRIMARY KEY,
                realized_pnl REAL DEFAULT 0,
                trades INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL, symbol TEXT NOT NULL,
                direction TEXT, confidence INTEGER, agents_aligned INTEGER,
                entry REAL, stop_loss REAL, take_profit REAL,
                rr_ratio REAL, ceo_reasoning TEXT,
                outcome TEXT DEFAULT 'open', closed_at TEXT, pnl_pct REAL
            )
        """)


class AuditAgent:
    def __init__(self, db_path: str = AUDIT_DB):
        self.db_path = db_path
        ensure_schema(db_path)

    def log_decision(self, symbol, decision, confidence, ta_bias,
                     sentiment_bias, risk_approved, risk_reason, price):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO decisions
                (ts, symbol, decision, confidence, ta_bias, sentiment_bias,
                 risk_approved, risk_reason, price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), symbol, decision, confidence,
                  ta_bias, sentiment_bias, 1 if risk_approved else 0,
                  risk_reason, price))

    def log_order(self, symbol, side, qty, entry, sl, tp,
                  order_id, status, raw_response):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO orders
                (ts, symbol, side, qty, entry, stop_loss, take_profit,
                 order_id, status, raw_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), symbol, side, qty, entry,
                  sl, tp, str(order_id), status,
                  json.dumps(raw_response)[:2000]))

    def log_signal(self, symbol, direction, confidence, aligned,
                   entry, sl, tp, rr, ceo_reasoning):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO signals
                (ts, symbol, direction, confidence, agents_aligned,
                 entry, stop_loss, take_profit, rr_ratio, ceo_reasoning)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), symbol, direction, confidence,
                  aligned, entry, sl, tp, rr, ceo_reasoning))

    def get_today_pnl(self) -> float:
        today = date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT realized_pnl FROM daily_pnl WHERE day = ?", (today,)
            ).fetchone()
        return float(row[0]) if row else 0.0

    def add_pnl(self, amount: float, trade_increment: int = 1):
        today = date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO daily_pnl (day, realized_pnl, trades)
                VALUES (?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    realized_pnl = realized_pnl + excluded.realized_pnl,
                    trades = trades + excluded.trades
            """, (today, amount, trade_increment))

    def count_open_orders_today(self) -> int:
        today = date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE ts LIKE ? AND status = 'New'",
                (f"{today}%",)
            ).fetchone()
        return int(row[0]) if row else 0
