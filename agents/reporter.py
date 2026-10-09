"""Reporter Agent — Telegram alerts with rich position details."""
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class ReporterAgent:
    def __init__(self):
        self.enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        if not self.enabled:
            print("[Reporter] Telegram not configured - console only")

    def _send(self, text):
        if not self.enabled:
            print(f"[Reporter:disabled] {text}")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID, "text": text,
                "parse_mode": "Markdown", "disable_web_page_preview": True,
            }, timeout=10)
        except Exception as e:
            print(f"[Reporter] Telegram send failed: {e}")

    def send_decision(self, decision, approved, reason):
        status = "APPROVED" if approved else f"REJECTED - {reason}"
        text = (
            f"*{decision['symbol']} - {decision['decision']}*\n"
            f"Price: `${decision['price']:,.2f}`\n"
            f"Confidence: {decision['confidence']}%\n"
            f"Risk: {status}"
        )
        self._send(text)

    def send_trade_plan(self, plan, order_result):
        ok = (order_result.get("dry_run") or order_result.get("code") == "00000")
        header = "ORDER SENT" if ok else "ORDER FAILED"
        order_id = (order_result.get("data") or {}).get("orderId") or "DRY_RUN"
        text = (
            f"*{header}*\n"
            f"`{plan['side']} {plan['qty']} {plan['symbol']}`\n"
            f"Entry: `${plan['entry']:,.2f}`\n"
            f"SL: `${plan['stop_loss']:,.2f}`\n"
            f"TP: `${plan['take_profit']:,.2f}`\n"
            f"Order ID: `{order_id}`"
        )
        self._send(text)

    def send_professional_signal(self, symbol, direction, confidence, entry,
                                  atr, analysts, ceo_reasoning):
        is_long = "BUY" in direction.upper()
        if is_long:
            entry_low = entry - 0.15 * atr
            entry_high = entry + 0.15 * atr
            sl = entry - 2.0 * atr
            tp1 = entry + 1.0 * atr
            tp2 = entry + 2.0 * atr
            tp3 = entry + 3.0 * atr
        else:
            entry_low = entry + 0.15 * atr
            entry_high = entry - 0.15 * atr
            sl = entry + 2.0 * atr
            tp1 = entry - 1.0 * atr
            tp2 = entry - 2.0 * atr
            tp3 = entry - 3.0 * atr
        risk = abs(entry - sl)
        reward = abs(tp3 - entry)
        rr = reward / risk if risk > 0 else 0
        pct = lambda t: abs(t - entry) / entry * 100
        emoji = "🟢" if is_long else "🔴"
        label = "LONG" if is_long else "SHORT"
        text = (
            f"{emoji} *SIGNAL - {symbol} ({label})*\n\n"
            f"🎯 Entry: `${entry_low:,.2f} - ${entry_high:,.2f}`\n"
            f"🛑 SL: `${sl:,.2f}` (-{pct(sl):.2f}%)\n"
            f"✅ TP1: `${tp1:,.2f}` (+{pct(tp1):.2f}%)\n"
            f"✅ TP2: `${tp2:,.2f}` (+{pct(tp2):.2f}%)\n"
            f"✅ TP3: `${tp3:,.2f}` (+{pct(tp3):.2f}%)\n"
            f"⚖️ R:R `1:{rr:.1f}`\n"
            f"🔥 Confidence `{confidence}%`\n\n"
            f"*Analysts:* {analysts}\n\n"
            f"*CEO:* {ceo_reasoning}"
        )
        self._send(text)

    def send_position_opened(self, plan, fill_price, order_id, strategy_name="Momentum Breakout", reason="20-day high breakout"):
        """Rich position opened alert with strategy, entry time, potential P&L."""
        entry = plan["entry"]
        sl = plan["stop_loss"]
        tp = plan["take_profit"]
        qty = plan.get("qty", 0)
        contracts = max(int(qty / 0.0001), 1) if "BTC" in plan["symbol"] else max(int(qty / 0.01), 1)

        # P&L calculations
        risk_pct = abs(entry - sl) / entry * 100
        reward_pct = abs(tp - entry) / entry * 100
        rr = reward_pct / risk_pct if risk_pct > 0 else 0

        # USDT amounts (based on Bitget Demo contract sizes)
        # 1 contract BTC = 0.0001 BTC → notional = entry * 0.0001
        notional_per_contract = entry * 0.0001 if "BTC" in plan["symbol"] else entry * 0.01
        total_notional = notional_per_contract * contracts

        max_loss_usdt = total_notional * (risk_pct / 100)
        max_gain_usdt = total_notional * (reward_pct / 100)

        # Position sizing info
        equity = 10000.0  # Bitget Demo
        risk_pct_equity = (max_loss_usdt / equity) * 100

        is_long = "buy" in plan["side"].lower()
        emoji = "🟢" if is_long else "🔴"
        label = "LONG" if is_long else "SHORT"
        direction = "BUY" if is_long else "SELL"

        # Get current time
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        text = (
            f"{emoji} *POSITION OPENED — {plan['symbol']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"📊 *Stratégie:* {strategy_name}\n"
            f"🎯 *Raison:* {reason}\n"
            f"🕐 *Ouverture:* {now}\n\n"

            f"💼 *Trade:*\n"
            f"• Direction: *{direction}* ({label})\n"
            f"• Contrats: `{contracts}`\n"
            f"• Notionnel: `${total_notional:,.2f}`\n"
            f"• Entry: `${entry:,.2f}`\n\n"

            f"🛑 *Stop-Loss:* `${sl:,.2f}` ({-risk_pct:+.2f}%)\n"
            f"🎯 *Take-Profit:* `${tp:,.2f}` ({reward_pct:+.2f}%)\n"
            f"⚖️ *R:R:* `1:{rr:.1f}`\n\n"

            f"💰 *Gains/Pertes potentiels:*\n"
            f"• Perte max: `-${max_loss_usdt:.2f} USDT`\n"
            f"• Gain max: `+${max_gain_usdt:.2f} USDT`\n"
            f"• Risque: `{risk_pct_equity:.2f}%` du capital\n\n"

            f"🆔 *Order ID:* `{order_id}`\n\n"

            f"📈 [Voir sur Bitget](https://www.bitget.com/fr/futures/usdt/"
            f"{plan['symbol'].replace('USDT', '-USDT')})"
        )
        self._send(text)
