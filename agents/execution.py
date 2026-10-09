"""Execution Agent — Bitget Demo with hard cap at 1 contract (demo limitation)."""
import uuid, json, math, time
from agents.bitget_client import BitgetClient
from config import BITGET_PRODUCT_TYPE, BITGET_MARGIN_COIN

_TICK_CACHE = {}
_CONTRACT_SIZE_CACHE = {}
_MAX_CONTRACTS = 1  # Bitget Demo limitation


class ExecutionAgent:
    def __init__(self, audit_agent):
        self.audit = audit_agent
        self.client = BitgetClient()

    def get_balance(self):
        try:
            r = self.client.private_get("/api/v2/mix/account/accounts",
                                        {"productType": BITGET_PRODUCT_TYPE})
            if r.get("code") != "00000":
                return {"ok": False, "error": r}
            for acc in r.get("data", []):
                if acc.get("marginCoin") == BITGET_MARGIN_COIN:
                    return {"ok": True, "usdt_balance": float(acc.get("available", 0))}
            return {"ok": True, "usdt_balance": 0.0}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _all_positions(self):
        try:
            r = self.client.private_get("/api/v2/mix/position/all-position",
                                        {"productType": BITGET_PRODUCT_TYPE,
                                         "marginCoin": BITGET_MARGIN_COIN})
            if r.get("code") != "00000":
                return []
            return r.get("data", [])
        except Exception:
            return []

    def has_open_position(self, symbol):
        for p in self._all_positions():
            if p.get("symbol") == symbol and float(p.get("total", 0)) != 0:
                return True
        return False

    def get_position(self, symbol):
        for p in self._all_positions():
            if p.get("symbol") == symbol and float(p.get("total", 0)) != 0:
                return p
        return {}

    def close_position(self, symbol):
        try:
            return self.client.private_post("/api/v2/mix/order/close-positions",
                                            {"symbol": symbol,
                                             "productType": BITGET_PRODUCT_TYPE,
                                             "marginCoin": BITGET_MARGIN_COIN})
        except Exception as e:
            return {"error": str(e)}

    def _get_tick_size(self, symbol):
        if symbol in _TICK_CACHE:
            return _TICK_CACHE[symbol]
        try:
            r = self.client.public_get("/api/v2/mix/market/contracts",
                                       {"productType": BITGET_PRODUCT_TYPE, "symbol": symbol})
            if r.get("code") == "00000" and r.get("data"):
                place = int(r["data"][0].get("pricePlace", 1))
                tick = 10 ** (-place)
                _TICK_CACHE[symbol] = tick
                return tick
        except Exception:
            pass
        _TICK_CACHE[symbol] = 0.1
        return 0.1

    def _round_price(self, price, tick):
        rounded = round(round(price / tick) * tick, 10)
        if tick >= 1:
            return str(int(rounded))
        dec = max(0, -int(round(math.log10(tick))))
        return f"{rounded:.{dec}f}"

    def _safe_post(self, path, body):
        try:
            return self.client.private_post(path, body)
        except Exception as e:
            resp = getattr(e, "response", None)
            if resp is not None:
                return {"http_status": resp.status_code, "body": resp.text}
            return {"exception": str(e)}

    def place_order(self, plan, dry_run=False):
        if dry_run:
            print(f"[Execution] DRY RUN: {plan}")
            return {"dry_run": True, "plan": plan}

        symbol = plan["symbol"]
        side = "buy" if plan["side"].lower() == "buy" else "sell"
        close_side = "sell" if side == "buy" else "buy"
        contracts = _MAX_CONTRACTS

        tick = self._get_tick_size(symbol)
        sl_str = self._round_price(plan["stop_loss"], tick)
        tp_str = self._round_price(plan["take_profit"], tick)

        # 1. Market entry
        entry_body = {
            "symbol": symbol, "productType": BITGET_PRODUCT_TYPE,
            "marginMode": "isolated", "marginCoin": BITGET_MARGIN_COIN,
            "size": str(contracts), "side": side, "tradeSide": "open",
            "orderType": "market", "clientOid": uuid.uuid4().hex[:20],
        }
        print(f"[Execution] 1/3 Market {contracts} contract(s)")
        r1 = self._safe_post("/api/v2/mix/order/place-order", entry_body)
        print(f"[Execution] Entry: {json.dumps(r1)[:300]}")

        if r1.get("code") != "00000":
            self.audit.log_order(symbol, side.upper(), contracts,
                                 plan["entry"], plan["stop_loss"], plan["take_profit"],
                                 "N/A", "Failed-Entry", r1)
            return r1

        entry_oid = r1["data"]["orderId"]
        time.sleep(2)

        # 2. Stop-loss
        sl_body = {
            "symbol": symbol, "productType": BITGET_PRODUCT_TYPE,
            "marginCoin": BITGET_MARGIN_COIN,
            "marginMode": "isolated", "planType": "normal_plan", "triggerPrice": sl_str,
            "triggerType": "mark_price", "side": close_side,
            "tradeSide": "close", "orderType": "market",
            "size": str(contracts), "clientOid": uuid.uuid4().hex[:20],
        }
        print(f"[Execution] 2/3 SL @ {sl_str}")
        r2 = self._safe_post("/api/v2/mix/order/place-plan-order", sl_body)
        print(f"[Execution] SL: {json.dumps(r2)[:200]}")

        # 3. Take-profit
        tp_body = sl_body.copy()
        tp_body["triggerPrice"] = tp_str
        tp_body["clientOid"] = uuid.uuid4().hex[:20]
        print(f"[Execution] 3/3 TP @ {tp_str}")
        r3 = self._safe_post("/api/v2/mix/order/place-plan-order", tp_body)
        print(f"[Execution] TP: {json.dumps(r3)[:200]}")

        self.audit.log_order(symbol, side.upper(), contracts,
                             plan["entry"], plan["stop_loss"], plan["take_profit"],
                             entry_oid, "New", {"entry": r1, "sl": r2, "tp": r3})

        return {"code": "00000", "data": {"orderId": entry_oid}}

    def close_all(self):
        closed = 0
        for p in self._all_positions():
            if float(p.get("total", 0)) != 0:
                self.close_position(p["symbol"])
                closed += 1
        return f"closed {closed} positions"
