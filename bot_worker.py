"""
Bot worker — one-shot. Processes new Telegram messages, exits.
Used by GitHub Actions for 24/7 operation.
"""
import requests
from pathlib import Path
from groq import Groq

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GROQ_API_KEY,
    DRY_RUN, STRATEGY_SYMBOLS, ACCOUNT_EQUITY_USDT,
    TARGET_CAPITAL, ADX_MIN, EMA_FAST, EMA_SLOW,
)

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
OFFSET_FILE = Path("logs/.bot_offset")
MODEL = "openai/gpt-oss-120b"


def get_balance_safe():
    try:
        from agents.audit import AuditAgent
        from agents.execution import ExecutionAgent
        ex = ExecutionAgent(AuditAgent())
        b = ex.get_balance()
        return b.get("usdt_balance", 0) if b.get("ok") else 0
    except Exception:
        return 0.0


def build_system_prompt():
    balance = get_balance_safe()
    mode = "DRY RUN (simulation)" if DRY_RUN else "LIVE DEMO (execution reelle)"
    return (
        "Tu es un assistant personnel senior, polyvalent et cultive.\n"
        "Tu reponds a TOUTES les questions, quel que soit le sujet "
        "(culture generale, sciences, code, finance, conseils, etc.).\n"
        "Tu es direct, concis (3-5 phrases sauf si on demande plus), naturel.\n\n"
        "CONTEXTE PROJET (utiliser si la question s'y rapporte) :\n"
        f"- Bot 'Crypto Agency' sur Bitget Demo.\n"
        f"- Strategie : EMA{EMA_FAST}/{EMA_SLOW} + ADX >= {ADX_MIN} sur BTC daily.\n"
        f"- Solde Bitget Demo : {balance:.2f} USDT.\n"
        f"- Objectif : {TARGET_CAPITAL:,.0f} USDT.\n"
        f"- Mode : {mode}."
    )


def send(chat_id, text):
    try:
        requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=10,
        )
    except Exception as e:
        print(f"Send failed: {e}")


def ask_groq(question):
    if not GROQ_API_KEY:
        return "Groq non configure."
    try:
        client = Groq(api_key=GROQ_API_KEY)
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": question},
            ],
            temperature=0.6,
            max_tokens=800,
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"Erreur Groq : {e}"


def main():
    offset = None
    if OFFSET_FILE.exists():
        try:
            offset = int(OFFSET_FILE.read_text().strip())
        except Exception:
            pass

    params = {"timeout": 5, "allowed_updates": '["message"]'}
    if offset:
        params["offset"] = offset

    try:
        r = requests.get(f"{TG_API}/getUpdates", params=params, timeout=20)
        updates = r.json().get("result", [])
    except Exception as e:
        print(f"getUpdates failed: {e}")
        return

    if not updates:
        print("No new messages.")
        return

    new_offset = offset or 0
    for u in updates:
        new_offset = u["update_id"] + 1
        msg = u.get("message") or u.get("edited_message")
        if not msg:
            continue
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if not text:
            continue

        if str(chat_id) != str(TELEGRAM_CHAT_ID):
            print(f"Ignoring unauthorized chat: {chat_id}")
            continue

        print(f"Q: {text[:80]}")
        if text.lower() in ("/start", "/help"):
            response = (
                "Assistant Senior\n\n"
                "Pose-moi n'importe quelle question.\n"
                "Exemples :\n"
                "- Explique-moi la photosynthese\n"
                "- Ecris un poeme sur l'automne\n"
                "- Ou en est mon bot de trading ?\n"
                "- Combien j'ai gagne ?"
            )
        else:
            response = ask_groq(text)

        send(chat_id, response)
        print(f"A: sent {len(response)} chars")

    OFFSET_FILE.parent.mkdir(exist_ok=True)
    OFFSET_FILE.write_text(str(new_offset))
    print(f"Offset saved: {new_offset}")


if __name__ == "__main__":
    main()
