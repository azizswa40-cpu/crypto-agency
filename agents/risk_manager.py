from config import (
    ACCOUNT_EQUITY_USDT, RISK_PER_TRADE_PCT, DAILY_LOSS_LIMIT_PCT,
    MAX_OPEN_POSITIONS, ATR_STOP_MULTIPLIER, ATR_TP_MULTIPLIER,
)


class RiskManagerAgent:
    def __init__(self, audit_agent):
        self.audit = audit_agent

    def veto_check(self, decision: dict) -> tuple:
        d = decision["decision"]

        if d not in ("STRONG BUY", "BUY", "WEAK BUY",
                     "STRONG SELL", "SELL", "WEAK SELL"):
            return False, f"Signal '{d}' is not a tradable direction"

        if decision["confidence"] < 55:
            return False, f"Confidence {decision['confidence']}% below 55% floor"

        today_pnl = self.audit.get_today_pnl()
        loss_limit = -abs(ACCOUNT_EQUITY_USDT * DAILY_LOSS_LIMIT_PCT / 100)
        if today_pnl <= loss_limit:
            return False, f"Daily loss limit hit: {today_pnl:.2f} USDT"

        open_count = self.audit.count_open_orders_today()
        if open_count >= MAX_OPEN_POSITIONS:
            return False, f"Max open positions reached ({open_count})"

        if decision.get("atr", 0) <= 0:
            return False, "ATR invalid"

        return True, "approved"

    def position_size(self, entry: float, stop_loss: float) -> float:
        risk_amount = ACCOUNT_EQUITY_USDT * RISK_PER_TRADE_PCT / 100
        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit <= 0:
            return 0.0
        return round(risk_amount / risk_per_unit, 6)

    def build_trade_plan(self, decision: dict) -> dict:
        entry = decision["price"]
        atr = decision["atr"]
        side = "Buy" if "BUY" in decision["decision"] else "Sell"

        if side == "Buy":
            stop_loss = entry - ATR_STOP_MULTIPLIER * atr
            take_profit = entry + ATR_TP_MULTIPLIER * atr
        else:
            stop_loss = entry + ATR_STOP_MULTIPLIER * atr
            take_profit = entry - ATR_TP_MULTIPLIER * atr

        qty = self.position_size(entry, stop_loss)

        return {
            "symbol": decision["symbol"],
            "side": side,
            "entry": entry,
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "qty": qty,
            "atr": atr,
            "confidence": decision["confidence"],
            "risk_usdt": ACCOUNT_EQUITY_USDT * RISK_PER_TRADE_PCT / 100,
        }
