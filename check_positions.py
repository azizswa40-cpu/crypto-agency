"""
Position monitor — detects closed positions, updates signals DB with REAL P&L,
sends detailed Telegram alerts, and cleans up orphan orders.
"""
import sqlite3
from datetime import datetime, timedelta
from config import AUDIT_DB, MAX_HOLD_DAYS
from agents.audit import ensure_schema

FEE_RATE = 0.0006 * 2  # 0.06% per side (taker) = 0.12% round trip


class PositionMonitor:
    def __init__(self, audit_agent, execu_agent, reporter_agent):
        self.audit = audit_agent
        self.execu = execu_agent
        self.reporter = reporter_agent
        ensure_schema(AUDIT_DB)

    def get_open_signals(self):
        conn = sqlite3.connect(AUDIT_DB)
        rows = conn.execute("""
            SELECT id, symbol, direction, entry, stop_loss, take_profit, ts
            FROM signals WHERE outcome = 'open'
        """).fetchall()
        conn.close()
        return rows

    def get_active_positions(self):
        try:
            r = self.execu._all_positions()
            result = {}
            for p in r:
                if float(p.get("total", 0)) != 0:
                    result[p["symbol"]] = p
            return result
        except Exception as e:
            print(f"[Monitor] get_positions failed: {e}")
            return {}

    def fetch_closed_pnl(self, symbol):
        """Try to get realized PnL from Bitget positions history."""
        try:
            r = self.execu.client.private_get(
                "/api/v2/mix/position/history-position",
                {"productType": "USDT-FUTURES", "symbol": symbol, "limit": "5"}
            )
            if r.get("code") != "00000":
                return None
            for item in r.get("data", {}).get("list", []):
                return {
                    "pnl": float(item.get("pnl", 0)),
                    "close_price": float(item.get("closePrice", 0)),
                    "open_price": float(item.get("openPriceAvg", 0)),
                    "updated": item.get("cTime"),
                }
        except Exception as e:
            print(f"[Monitor] PnL fetch failed: {e}")
        return None

    def close_position_now(self, symbol, reason="timeout"):
        try:
            r = self.execu.close_position(symbol)
            print(f"[Monitor] Closed {symbol}: {r.get('code')} {r.get('msg')}")
            return r
        except Exception as e:
            print(f"[Monitor] Close failed: {e}")
            return {"error": str(e)}

    def cleanup_orphan_orders(self):
        """Cancel pending orders older than 24h."""
        try:
            r = self.execu.client.private_get(
                "/api/v2/mix/order/orders-pending",
                {"productType": "USDT-FUTURES"}
            )
            if r.get("code") != "00000":
                return 0
            orders = (r.get("data") or {}).get("entrustedList") or []
            now_ms = int(datetime.now().timestamp() * 1000)
            cutoff = now_ms - 24 * 3600 * 1000
            cancelled = 0
            for o in orders:
                ctime = int(o.get("cTime", 0))
                if ctime < cutoff:
                    self.execu.client.private_post(
                        "/api/v2/mix/order/cancel-order",
                        {"symbol": o["symbol"], "productType": "USDT-FUTURES",
                         "orderId": o["orderId"]}
                    )
                    cancelled += 1
                    print(f"[Monitor] Cancelled orphan order {o['orderId']}")
            return cancelled
        except Exception as e:
            print(f"[Monitor] Cleanup failed: {e}")
            return 0

    def check(self):
        # 1. Cleanup orphan orders first
        self.cleanup_orphan_orders()

        # 2. Check open signals
        open_signals = self.get_open_signals()
        if not open_signals:
            print("[Monitor] No open signals to check.")
            return

        active = self.get_active_positions()
        print(f"[Monitor] {len(open_signals)} open signals, {len(active)} active positions.")

        for (sid, symbol, direction, entry, sl, tp, ts) in open_signals:
            # Timeout check first
            try:
                open_dt = datetime.fromisoformat(ts)
            except Exception:
                open_dt = datetime.utcnow()

            if datetime.utcnow() - open_dt > timedelta(days=MAX_HOLD_DAYS):
                print(f"[Monitor] {symbol} hit {MAX_HOLD_DAYS}d timeout — closing.")
                self.close_position_now(symbol, "timeout")
                conn = sqlite3.connect(AUDIT_DB)
                conn.execute("""
                    UPDATE signals SET outcome='timeout', closed_at=?
                    WHERE id=?
                """, (datetime.utcnow().isoformat(), sid))
                conn.commit()
                conn.close()
                self.reporter._send(
                    f"⏰ *POSITION TIMEOUT*\n"
                    f"`{symbol}` {direction}\n"
                    f"Held {MAX_HOLD_DAYS} days — force closed.\n"
                    f"Entry: `${entry:,.2f}`"
                )
                continue

            # Position no longer exists = closed by SL/TP
            if symbol not in active:
                info = self.fetch_closed_pnl(symbol)
                if info and info["close_price"] > 0:
                    close_price = info["close_price"]
                    pnl_usdt = info["pnl"]
                else:
                    close_price = entry
                    pnl_usdt = 0

                pnl_pct = (close_price - entry) / entry * 100
                if "SELL" in direction.upper():
                    pnl_pct = -pnl_pct
                pnl_pct_net = pnl_pct - (FEE_RATE * 100)

                if pnl_pct_net > 0.3:
                    outcome = "win"
                    emoji = "✅"
                elif pnl_pct_net < -0.3:
                    outcome = "loss"
                    emoji = "❌"
                else:
                    outcome = "breakeven"
                    emoji = "⚪"

                conn = sqlite3.connect(AUDIT_DB)
                conn.execute("""
                    UPDATE signals SET outcome=?, closed_at=?, pnl_pct=?
                    WHERE id=?
                """, (outcome, datetime.utcnow().isoformat(), pnl_pct_net, sid))
                conn.commit()
                conn.close()

                # Determine if hit SL or TP
                hit = "unknown"
                if outcome == "win":
                    hit = "TP"
                elif outcome == "loss":
                    hit = "SL"

                self.reporter._send(
                    f"{emoji} *POSITION CLOSED — {hit}*\n"
                    f"`{symbol}` {direction}\n"
                    f"Entry:  `${entry:,.2f}`\n"
                    f"Close:  `${close_price:,.2f}`\n"
                    f"P&L:    `{pnl_pct_net:+.2f}%` (after fees)\n"
                    f"USDT:   `${pnl_usdt:+.2f}`\n"
                    f"Outcome: *{outcome.upper()}*"
                )
            else:
                print(f"[Monitor] {symbol} still open.")


if __name__ == "__main__":
    from agents.audit import AuditAgent
    from agents.execution import ExecutionAgent
    from agents.reporter import ReporterAgent

    audit = AuditAgent()
    execu = ExecutionAgent(audit)
    reporter = ReporterAgent()
    monitor = PositionMonitor(audit, execu, reporter)
    monitor.check()
