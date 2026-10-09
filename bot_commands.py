"""Extra commands for the Telegram bot with rich position details."""
import sqlite3
from pathlib import Path
from datetime import datetime
from config import AUDIT_DB

FEE_RATE = 0.0006  # 0.06% per side (taker)


def cmd_help():
    return (
        "*Assistant Crypto Agency*\n\n"
        "*Commandes :*\n"
        "/balance - Solde Bitget Demo\n"
        "/positions - Positions ouvertes (detail)\n"
        "/pnl - P&L detaille par position\n"
        "/signals - Derniers signaux\n"
        "/decisions - Dernieres decisions\n"
        "/arena - Resultats de l'arene\n"
        "/help - Cette aide\n\n"
        "Pose aussi des questions libres."
    )


def _load_positions():
    """Return list of active positions with rich data."""
    try:
        from agents.audit import AuditAgent
        from agents.execution import ExecutionAgent
        ex = ExecutionAgent(AuditAgent())
        positions = ex._all_positions()
    except Exception as e:
        return [], str(e)

    active = []
    for p in positions:
        size = float(p.get("total", 0))
        if size == 0:
            continue
        entry = float(p.get("openPriceAvg", 0))
        mark = float(p.get("markPrice", entry))
        # Bitget position fields
        unrealized = float(p.get("unrealizedPL", 0))
        margin = float(p.get("margin", 0))
        leverage = p.get("leverage", "?")
        side = p.get("holdSide", "?").upper()
        symbol = p.get("symbol", "?")
        # P&L %
        if entry > 0:
            pnl_pct = (mark - entry) / entry * 100
            if side == "SHORT":
                pnl_pct = -pnl_pct
        else:
            pnl_pct = 0.0

        # Estimate notional: how much capital is engaged
        notional = size * entry
        # Fees (round trip estimate)
        fees_est = notional * FEE_RATE * 2

        active.append({
            "symbol": symbol,
            "side": side,
            "size": size,
            "entry": entry,
            "mark": mark,
            "pnl_pct": pnl_pct,
            "pnl_usdt": unrealized,
            "margin": margin,
            "notional": notional,
            "fees_est": fees_est,
            "leverage": leverage,
        })
    return active, None


def cmd_balance():
    try:
        from agents.audit import AuditAgent
        from agents.execution import ExecutionAgent
        ex = ExecutionAgent(AuditAgent())
        b = ex.get_balance()
        bal = b.get("usdt_balance", 0) if b.get("ok") else 0
        return (
            f"*Solde Bitget Demo*\n\n"
            f"`{bal:.2f} USDT`\n\n"
            f"Objectif: 100000 USDT\n"
            f"Progression: {bal/100000*100:.2f}%"
        )
    except Exception as e:
        return f"Erreur: {e}"


def cmd_positions():
    """Detailed open positions."""
    active, err = _load_positions()
    if err:
        return f"Erreur: {err}"
    if not active:
        return "Aucune position ouverte."

    lines = [f"*Positions ouvertes* ({len(active)})", ""]
    for p in active:
        emoji = "🟢" if p["pnl_usdt"] >= 0 else "🔴"
        lines.append(
            f"{emoji} *{p['symbol']}* — {p['side']}\n"
            f"  📥 Entry: `{p['entry']:,.4f}`\n"
            f"  📊 Mark:  `{p['mark']:,.4f}`\n"
            f"  📦 Size:  `{p['size']}` contrats\n"
            f"  💰 Notionnel: `${p['notional']:,.2f}`\n"
            f"  💵 Marge: `${p['margin']:,.2f}`\n"
            f"  ⚡ Levier: `{p['leverage']}x`\n"
            f"  📈 P&L: `{p['pnl_usdt']:+.4f} USDT` ({p['pnl_pct']:+.2f}%)\n"
            f"  🧾 Frais estimés: `${p['fees_est']:.4f}`"
        )
    return "\n\n".join(lines)


def cmd_pnl():
    """P&L summary across all positions."""
    active, err = _load_positions()
    if err:
        return f"Erreur: {err}"
    if not active:
        return "Aucune position ouverte. P&L = 0."

    total_pnl = sum(p["pnl_usdt"] for p in active)
    total_notional = sum(p["notional"] for p in active)
    total_fees = sum(p["fees_est"] for p in active)
    total_margin = sum(p["margin"] for p in active)

    emoji = "🟢" if total_pnl >= 0 else "🔴"

    lines = [
        f"{emoji} *P&L Total*",
        "",
        f"Positions ouvertes: `{len(active)}`",
        f"Capital engagé: `${total_margin:,.2f} USDT`",
        f"Notionnel total: `${total_notional:,.2f} USDT`",
        f"P&L non réalisé: `{total_pnl:+.4f} USDT`",
        f"Frais estimés: `-${total_fees:.4f} USDT`",
        f"*P&L net estimé: `{total_pnl - total_fees:+.4f} USDT`*",
        "",
    ]
    for p in active:
        lines.append(
            f"• *{p['symbol']}* {p['side']}: `{p['pnl_usdt']:+.4f}` "
            f"({p['pnl_pct']:+.2f}%)"
        )
    return "\n".join(lines)


def cmd_signals():
    if not Path(AUDIT_DB).exists():
        return "Aucun signal enregistre."
    conn = sqlite3.connect(AUDIT_DB)
    try:
        rows = conn.execute(
            "SELECT ts, symbol, direction, entry, outcome, pnl_pct "
            "FROM signals ORDER BY ts DESC LIMIT 8"
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    if not rows:
        return "Aucun signal enregistre."
    lines = ["*Derniers signaux*", ""]
    for (ts, sym, d, entry, out, pnl) in rows:
        emoji = {"win": "✅", "loss": "❌", "open": "🟢", "test": "🧪", "closed": "⚪"}.get(out, "•")
        pnl_str = f" | PnL {pnl:+.2f}%" if pnl else ""
        lines.append(f"{emoji} {ts[:10]} *{sym}* {d}{pnl_str}")
    return "\n".join(lines)


def cmd_decisions():
    if not Path(AUDIT_DB).exists():
        return "Aucune decision enregistree."
    conn = sqlite3.connect(AUDIT_DB)
    try:
        rows = conn.execute(
            "SELECT ts, symbol, decision, confidence "
            "FROM decisions ORDER BY ts DESC LIMIT 8"
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    if not rows:
        return "Aucune decision enregistree."
    lines = ["*Dernieres decisions*", ""]
    for (ts, sym, d, conf) in rows:
        lines.append(f"• {ts[:10]} *{sym}* → {d} ({conf}%)")
    return "\n".join(lines)


def cmd_arena():
    logs = Path("logs")
    files = sorted(logs.glob("arena_*.csv"), reverse=True)
    if not files:
        return "Aucun resultat d'arene."
    try:
        import pandas as pd
        df = pd.read_csv(files[0])
        lines = [f"*Arene — {files[0].name}*", ""]
        for _, r in df.head(5).iterrows():
            lines.append(
                f"*{r['strategy']}*\n"
                f"  Return: {r['ret_pct']:+.1f}% | PF: {r['pf']:.2f}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Erreur: {e}"


COMMANDS = {
    "/start": cmd_help,
    "/help": cmd_help,
    "/balance": cmd_balance,
    "/positions": cmd_positions,
    "/pnl": cmd_pnl,
    "/signals": cmd_signals,
    "/decisions": cmd_decisions,
    "/arena": cmd_arena,
}


def handle(text):
    cmd = text.strip().lower().split()[0] if text.strip() else ""
    if cmd in COMMANDS:
        try:
            return COMMANDS[cmd]()
        except Exception as e:
            return f"Erreur: {e}"
    return None
