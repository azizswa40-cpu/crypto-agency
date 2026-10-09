"""
Bot server — injects live ensemble data into Groq context.
Knows about 5 voting agents + 4 analysts + CEO + Risk Manager.
"""
import os, time, threading, requests, json
from pathlib import Path
from flask import Flask, jsonify
from groq import Groq

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GROQ_API_KEY,
    DRY_RUN, SIGNAL_ONLY_MODE, STRATEGY_SYMBOLS, ACCOUNT_EQUITY_USDT, TARGET_CAPITAL,
)
import bot_commands

app = Flask(__name__)
TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
OFFSET_FILE = Path("logs/.bot_offset")
VOTES_FILE = Path("logs/votes.json")
MODEL = "openai/gpt-oss-120b"
BOT_STATS = {"messages": 0, "last_message": None, "started_at": time.time()}


def get_balance():
    try:
        from agents.audit import AuditAgent
        from agents.execution import ExecutionAgent
        ex = ExecutionAgent(AuditAgent())
        b = ex.get_balance()
        return b.get("usdt_balance", 0) if b.get("ok") else 0
    except Exception:
        return 0.0


def get_positions_live():
    try:
        from agents.audit import AuditAgent
        from agents.execution import ExecutionAgent
        ex = ExecutionAgent(AuditAgent())
        positions = ex._all_positions()
    except Exception:
        return []
    out = []
    for p in positions:
        size = float(p.get("total", 0))
        if size == 0:
            continue
        entry = float(p.get("openPriceAvg", 0))
        mark = float(p.get("markPrice", entry))
        unrealized = float(p.get("unrealizedPL", 0))
        side = p.get("holdSide", "?").upper()
        pnl_pct = (mark - entry) / entry * 100 if entry > 0 else 0
        if side == "SHORT":
            pnl_pct = -pnl_pct
        out.append({
            "symbol": p.get("symbol"), "side": side, "size": size,
            "entry": entry, "mark": mark,
            "pnl_usdt": unrealized, "pnl_pct": pnl_pct,
        })
    return out


def get_latest_ensemble():
    """Read the latest ensemble vote result."""
    if not VOTES_FILE.exists():
        return None
    try:
        with open(VOTES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_signals_recent(limit=10):
    import sqlite3
    from config import AUDIT_DB
    if not Path(AUDIT_DB).exists():
        return []
    conn = sqlite3.connect(AUDIT_DB)
    try:
        rows = conn.execute(
            "SELECT ts, symbol, direction, entry, outcome, pnl_pct "
            "FROM signals ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    return rows


def build_live_context():
    """Rich context with ALL live data — agents, analysts, CEO, Risk."""
    balance = get_balance()
    positions = get_positions_live()
    signals = get_signals_recent(10)
    ensemble = get_latest_ensemble()

    ctx = [
        "ARCHITECTURE DU SYSTEME (Crypto Agency v3) :",
        "",
        "Le systeme utilise 11 agents IA organises en 3 couches :",
        "",
        "1) STRATEGY LAYER — 5 agents votants (chacun vote BUY/SELL/HOLD) :",
        "   - Momentum Agent (cassure 20-day high/low)",
        "   - Trend Agent (EMA50/200 + ADX >= 22)",
        "   - Liquidity Agent (stop-hunts, sweeps)",
        "   - Funding Agent (contrarian sur funding rate negatif)",
        "   - Mean Rev Agent (RSI < 30 + Bollinger bas)",
        "",
        "2) ANALYST LAYER — 4 analystes de contexte :",
        "   - Technical Analyst (RSI, MACD, EMA, Bollinger)",
        "   - Sentiment Analyst (Fear & Greed + news)",
        "   - OnChain Analyst (funding rate + open interest)",
        "   - Fundamental Analyst (BTC dominance + macro)",
        "",
        "3) DECISION LAYER :",
        "   - CEO Office (synthese des 5 votes + poids par regime)",
        "   - Risk Manager (veto hard-code : max drawdown 15%, 3 pertes max, cooldown 24h, 1 trade/jour)",
        "",
        "MODE ACTUEL : signal-only (aucun ordre automatique)",
        "",
        "DONNEES LIVE :",
        f"- Solde Bitget Demo : {balance:.4f} USDT",
        f"- Objectif : {TARGET_CAPITAL:,.0f} USDT",
        f"- Progression : {balance/TARGET_CAPITAL*100:.4f}%",
        f"- Symboles suivis : {', '.join(STRATEGY_SYMBOLS)}",
        f"- DRY_RUN : {DRY_RUN}",
        f"- SIGNAL_ONLY_MODE : {SIGNAL_ONLY_MODE}",
        "",
    ]

    if ensemble:
        ctx.append(f"DERNIER SCAN ENSEMBLE :")
        ctx.append(f"- Timestamp : {ensemble.get('timestamp', '?')[:19]}")
        ctx.append(f"- Prix BTC : ${ensemble.get('price', 0):,.2f}")
        ctx.append(f"- Decision : {ensemble.get('decision', '?')}")
        ctx.append(f"- Regime : {ensemble.get('regime', '?')}")
        ctx.append(f"- Votes : BUY {ensemble.get('buy_count', 0)}/5 | SELL {ensemble.get('sell_count', 0)}/5")
        ctx.append(f"- Volatilite : {ensemble.get('vol_pct', 0)}%")
        ctx.append(f"- Blackout news : {ensemble.get('blackout', False)}")
        ctx.append("")
        ctx.append("Détail des 5 agents :")
        for v in ensemble.get("votes", []):
            ctx.append(f"  • {v.get('name')} : {v.get('action')} — {v.get('reason')}")
        ctx.append("")
        ctx.append("Détail des 4 analystes :")
        analysts = ensemble.get("analysts", {})
        for name, info in analysts.items():
            ctx.append(f"  • {name} : {info.get('bias')} — {info.get('detail')}")
        ctx.append("")
    else:
        ctx.append("Aucun scan ensemble encore enregistre (logs/votes.json vide).")
        ctx.append("")

    ctx.append(f"POSITIONS OUVERTES : {len(positions)}")
    for p in positions:
        ctx.append(
            f"- {p['symbol']} {p['side']} | Size {p['size']} | "
            f"Entry ${p['entry']:.4f} | Mark ${p['mark']:.4f} | "
            f"P&L {p['pnl_usdt']:+.4f} USDT ({p['pnl_pct']:+.2f}%)"
        )
    if not positions:
        ctx.append("- Aucune position ouverte")
    ctx.append("")

    ctx.append(f"HISTORIQUE DES SIGNAUX ({len(signals)}) :")
    for (ts, sym, d, entry, out, pnl) in signals:
        ctx.append(f"- {ts[:10]} {sym} {d} entry ${entry:,.2f} -> {out}")

    return "\n".join(ctx)


SYSTEM_BASE = """Tu es l'assistant personnel du projet Crypto Agency.
Tu connais l'architecture complète :
- 5 agents votants (Momentum, Trend, Liquidity, Funding, Mean Rev)
- 4 analystes (Technical, Sentiment, OnChain, Fundamental)
- 1 CEO (decision) + 1 Risk Manager (veto)

REGLES DE REPONSE :
- Si on te demande combien de strategies : "5 agents votants + 4 analystes = 9 strategies actives".
- Utilise UNIQUEMENT les donnees live ci-dessous pour les chiffres.
- Si une position est ouverte, donne son P&L exact en USDT et %.
- Si aucune position, dis-le clairement.
- Reponds en francais, concis (3-6 phrases).
- Tu peux aussi repondre a des questions generales (culture, code, etc.).

"""


def ask_groq(question):
    if not GROQ_API_KEY:
        return "Groq non configure."
    try:
        client = Groq(api_key=GROQ_API_KEY)
        live = build_live_context()
        full_system = SYSTEM_BASE + live
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"Erreur Groq : {e}"


def send(chat_id, text):
    try:
        requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=10,
        )
    except Exception as e:
        print(f"[Send] {e}")


def load_offset():
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except Exception:
            return None
    return None


def save_offset(o):
    try:
        OFFSET_FILE.parent.mkdir(exist_ok=True)
        OFFSET_FILE.write_text(str(o))
    except Exception:
        pass


def bot_loop():
    print("[Bot] Listener starting...")
    offset = load_offset()
    while True:
        try:
            params = {"timeout": 25, "allowed_updates": '["message"]'}
            if offset:
                params["offset"] = offset
            r = requests.get(f"{TG_API}/getUpdates", params=params, timeout=30)
            updates = r.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                save_offset(offset)
                msg = u.get("message") or u.get("edited_message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "").strip()
                if not text:
                    continue
                if str(chat_id) != str(TELEGRAM_CHAT_ID):
                    print(f"[Bot] Unauthorized: {chat_id}")
                    continue
                BOT_STATS["messages"] += 1
                BOT_STATS["last_message"] = text[:100]
                print(f"[Bot] Q: {text[:80]}")
                response = bot_commands.handle(text)
                if response is None:
                    response = ask_groq(text)
                send(chat_id, response)
                print(f"[Bot] A: {len(response)} chars")
        except Exception as e:
            print(f"[Bot] Loop error: {e}")
            time.sleep(3)


@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "uptime": int(time.time() - BOT_STATS["started_at"]),
        "messages": BOT_STATS["messages"],
        "positions": len(get_positions_live()),
        "balance": get_balance(),
        "agents": ["Momentum", "Trend", "Liquidity", "Funding", "MeanRev"],
        "analysts": ["Technical", "Sentiment", "OnChain", "Fundamental"],
    })


@app.route("/health")
def health():
    return "OK", 200


threading.Thread(target=bot_loop, daemon=True).start()
print("[Server] Bot thread started")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
