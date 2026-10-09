"""
Telegram bot listener — assistant senior polyvalent + accès au projet.
"""
import time
import requests
from pathlib import Path
from groq import Groq

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GROQ_API_KEY,
    AUDIT_DB, DRY_RUN, STRATEGY_SYMBOLS, ACCOUNT_EQUITY_USDT,
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
        "Tu reponds a TOUTES les questions de l'utilisateur, quel que soit le sujet "
        "(culture generale, sciences, code, finance, conseils, etc.).\n"
        "Tu es direct, concis (3-5 phrases sauf si on demande plus), et naturel.\n"
        "Tu n'es PAS limite a un projet : tu es un veritable compagnon intellectuel.\n\n"
        "CONTEXTE DU PROJET DE L'UTILISATEUR (a utiliser si la question s'y rapporte) :\n"
        f"- Bot de trading crypto 'Crypto Agency'.\n"
        f"- Tourne sur Bitget Demo (argent virtuel).\n"
        f"- Strategie : EMA{EMA_FAST}/{EMA_SLOW} + ADX >= {ADX_MIN} sur BTC daily.\n"
        f"- Solde actuel Bitget Demo : {balance:.2f} USDT.\n"
        f"- Objectif symbolique : {TARGET_CAPITAL:,.0f} USDT.\n"
        f"- Mode : {mode}.\n"
        f"- Tu peux repondre a des questions sur le bot, mais aussi sur tout autre sujet."
    )


def tg_send(chat_id, text):
    try:
        requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=10,
        )
    except Exception as e:
        print(f"[Bot] Send failed: {e}")


def tg_get_updates(offset=None):
    params = {"timeout": 25}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(f"{TG_API}/getUpdates", params=params, timeout=30)
        return r.json().get("result", [])
    except Exception:
        return []


def load_offset():
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except Exception:
            return None
    return None


def save_offset(offset):
    OFFSET_FILE.parent.mkdir(exist_ok=True)
    OFFSET_FILE.write_text(str(offset))


def ask_groq(question):
    if not GROQ_API_KEY:
        return "Groq n'est pas configure."
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


def handle_message(chat_id, text):
    text = text.strip()
    if not text:
        return

    if str(chat_id) != str(TELEGRAM_CHAT_ID):
        tg_send(chat_id, "Acces reserve au proprietaire.")
        print(f"[Bot] Unauthorized: {chat_id}")
        return

    print(f"[Bot] Message from {chat_id}: {text[:80]}")

    if text.lower() in ("/start", "/help"):
        response = (
            "Assistant Senior\n\n"
            "Pose-moi n'importe quelle question, sur n'importe quel sujet.\n"
            "Exemples :\n"
            "- Explique-moi la photosynthese\n"
            "- Ecris un poeme sur l'automne\n"
            "- Ou en est mon bot de trading ?\n"
            "- Combien j'ai gagne ?\n"
            "- Comment fonctionne l'ADX ?"
        )
    else:
        response = ask_groq(text)

    tg_send(chat_id, response)


def main():
    print("=" * 60)
    print("  TELEGRAM BOT LISTENER — Assistant Senior")
    print("=" * 60)
    print("  Listening... Ctrl+C to stop")
    print("=" * 60)

    offset = load_offset()
    while True:
        try:
            updates = tg_get_updates(offset)
            for u in updates:
                offset = u["update_id"] + 1
                save_offset(offset)
                msg = u.get("message") or u.get("edited_message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")
                if text:
                    handle_message(chat_id, text)
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Bot] Stopped.")
            break
        except Exception as e:
            print(f"[Bot] Loop error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
