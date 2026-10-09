"""Force test - bypass golden cross, buy if in uptrend + ADX >= 10."""
from agents.market_data import MarketDataAgent
from agents.audit import AuditAgent
from agents.risk_manager import RiskManagerAgent
from agents.execution import ExecutionAgent
from agents.reporter import ReporterAgent
from strategy import compute_indicators
from config import EMA_FAST, EMA_SLOW

audit = AuditAgent()
rm = RiskManagerAgent(audit)
execu = ExecutionAgent(audit)
reporter = ReporterAgent()

symbol = "BTCUSDT"
df = MarketDataAgent(symbol, interval="1D").fetch_candles()

if df.empty:
    print("No data from Bitget")
    exit(1)

d = compute_indicators(df, ema_fast=EMA_FAST, ema_slow=EMA_SLOW).dropna()
last = d.iloc[-1]

price = float(last["close"])
ema_fast = float(last["ema_fast"])
ema_slow = float(last["ema_slow"])
adx = float(last["adx"])
atr = float(last["atr"])

print(f"Price:     ${price:,.2f}")
print(f"EMA{EMA_FAST}:   ${ema_fast:,.2f}")
print(f"EMA{EMA_SLOW}:  ${ema_slow:,.2f}")
print(f"ADX:        {adx:.1f}")
print(f"ATR:        ${atr:,.2f}")
print()

if ema_fast <= ema_slow:
    print("Not in uptrend - cannot force BUY")
    exit(0)

if adx < 10:
    print(f"ADX {adx:.1f} < 10 - cannot force BUY")
    exit(0)

print(">> In uptrend + ADX sufficient - forcing BUY")
print()

decision = {
    "symbol": symbol, "decision": "BUY", "confidence": 90,
    "ta_bias": "BULLISH", "sentiment_bias": "N/A",
    "price": price, "atr": atr, "reasons": ["FORCED TEST"],
}

approved, reason = rm.veto_check(decision)
print(f"Risk check: {approved} - {reason}")

if not approved:
    print("Risk veto - cannot trade")
    exit(0)

plan = rm.build_trade_plan(decision)
print(f"Plan: BUY {plan['qty']} {plan['symbol']}")
print(f"Entry: ${plan['entry']:,.2f}")
print(f"SL:    ${plan['stop_loss']:,.2f}")
print(f"TP:    ${plan['take_profit']:,.2f}")
print()

print("--- Placing order on Bitget Demo ---")
result = execu.place_order(plan, dry_run=False)
print(f"Code: {result.get('code')} | Msg: {result.get('msg')}")

if result.get("code") == "00000":
    oid = (result.get("data") or {}).get("orderId", "N/A")
    print(f"ORDER PLACED: {oid}")

    audit.log_signal(symbol, "BUY", 90, 1, plan["entry"], plan["stop_loss"],
                     plan["take_profit"], 3.0, "FORCED TEST")
    print("Signal logged to DB")

    reporter.send_position_opened(plan, plan["entry"], oid)
    print("Telegram alert sent")

    print()
    print("Check Bitget: https://www.bitget.com/fr/futures/usdt/BTCUSDT")
    print("Tab: Positions")
else:
    print(f"Order failed")
    print(f"Full response: {result}")
