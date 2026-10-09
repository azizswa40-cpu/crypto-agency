"""
Execution Agent — OKX Demo Trading.
Handles positions, closures, timeouts, and kill switch.
"""
import okx.Trade as Trade
import okx.Account as Account
from config import (
    OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE, OKX_FLAG,
    OKX_TD_MODE, OKX_SYMBOL_MAP, OKX_CONTRACT_SIZE,
)


class ExecutionAgent:
    def __init__(self, audit_agent):
        self.audit = audit_agent
        if not all([OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE]):
            raise ValueError("OKX credentials missing in .env")
        self.trade = Trade.TradeAPI(OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE, False, OKX_FLAG)
        self.account = Account.AccountAPI(OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE, False, OKX_FLAG)

    def _okx_symbol(self, symbol: str) -> str:
        return OKX_SYMBOL_MAP.get(symbol.upper(), symbol)

    def _to_contracts(self, okx_symbol: str, qty_base: float) -> int:
        cs = OKX_CONTRACT_SIZE.get(okx_symbol, 1.0)
        return max(int(qty_base / cs), 1)

    def get_balance(self) -> dict:
        try:
            r = self.account.get_account_balance(ccy="USDT")
            if r.get("code") != "0":
                return {"ok": False, "error": r}
            d = r["data"][0].get("details", [])
            u = next((x for x in d if x["ccy"] == "USDT"), None)
            return {"ok": True, "usdt_balance": float(u["availBal"]) if u else 0.0}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def has_open_position(self, symbol: str) -> bool:
        """Check if a position is already open on this symbol."""
        try:
            okx_sym = self._okx_symbol(symbol)
            r = self.account.get_positions(instType="SWAP", instId=okx_sym)
            if r.get("code") != "0":
                return False
            for p in r.get("data", []):
                if float(p.get("pos", 0)) != 0:
                    return True
            return False
        except Exception as e:
            print(f"[Execution] Position check failed: {e}")
            return False

    def get_position(self, symbol: str) -> dict:
        """Get full position details."""
        try:
            okx_sym = self._okx_symbol(symbol)
            r = self.account.get_positions(instType="SWAP", instId=okx_sym)
            if r.get("code") != "0":
                return {}
            for p in r.get("data", []):
                if float(p.get("pos", 0)) != 0:
                    return p
            return {}
        except Exception as e:
            print(f"[Execution] get_position failed: {e}")
            return {}

    def close_position(self, symbol: str) -> dict:
        """Close position via market order (OKX close_positions)."""
        try:
            okx_sym = self._okx_symbol(symbol)
            r = self.trade.close_positions(instId=okx_sym, mgnMode=OKX_TD_MODE)
            return r
        except Exception as e:
            return {"error": str(e)}

    def place_order(self, plan: dict, dry_run: bool = False) -> dict:
        if dry_run:
            print(f"[Execution] DRY RUN — would place: {plan}")
            return {"dry_run": True, "plan": plan}
        okx_symbol = self._okx_symbol(plan["symbol"])
        side = "buy" if plan["side"].lower() == "buy" else "sell"
        contracts = self._to_contracts(okx_symbol, plan["qty"])
        try:
            order = self.trade.place_order(
                instId=okx_symbol, tdMode=OKX_TD_MODE, side=side,
                ordType="market", sz=str(contracts),
                attachAlgoOrds=[{
                    "slTriggerPx": str(plan["stop_loss"]), "slOrdPx": "-1",
                    "tpTriggerPx": str(plan["take_profit"]), "tpOrdPx": "-1",
                }],
            )
            order_id = (order.get("data") or [{}])[0].get("ordId", "N/A") if order.get("code") == "0" else "N/A"
            status = "New" if order.get("code") == "0" else "Failed"
            self.audit.log_order(plan["symbol"], side.upper(), contracts,
                                 plan["entry"], plan["stop_loss"], plan["take_profit"],
                                 order_id, status, order)
            return order
        except Exception as e:
            self.audit.log_order(plan["symbol"], side.upper(), contracts,
                                 plan["entry"], plan["stop_loss"], plan["take_profit"],
                                 "N/A", f"Error: {e}", {"error": str(e)})
            return {"error": str(e)}

    def get_closed_pnl(self, symbol: str) -> dict:
        """Fetch realized PnL from OKX positions history."""
        try:
            okx_sym = self._okx_symbol(symbol)
            r = self.account.get_positions_history(instType="SWAP", instId=okx_sym, limit="5")
            if r.get("code") != "0":
                return {}
            for item in r.get("data", []):
                return {
                    "pnl": float(item.get("realizedPnl", 0)),
                    "close_price": float(item.get("closeAvgPx", 0)),
                    "open_price": float(item.get("openAvgPx", 0)),
                }
        except Exception as e:
            print(f"[Execution] PnL fetch failed: {e}")
        return {}

    def close_all(self):
        """Emergency close all open positions (kill switch)."""
        try:
            positions = self.account.get_positions(instType="SWAP")
            if positions.get("code") != "0":
                return f"error: {positions}"
            closed = 0
            for p in positions["data"]:
                if float(p.get("pos", 0)) != 0:
                    self.trade.close_positions(
                        instId=p["instId"], mgnMode=OKX_TD_MODE,
                        posSide=p.get("posSide", "net"), autoCxl=True)
                    closed += 1
            return f"closed {closed} positions"
        except Exception as e:
            return f"error: {e}"
