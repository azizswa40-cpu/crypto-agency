import os
from dotenv import load_dotenv
load_dotenv()

# ── Strategy ─────────────────────────────────────────────
STRATEGY_SYMBOLS = ["BTCUSDT"]
STRATEGY_INTERVAL = "1D"
CANDLE_LIMIT = 2000
EMA_FAST = 50
EMA_SLOW = 200
ADX_MIN = 22
ATR_SL_MULT = 2.0
ATR_TP_MULT = 6.0
MAX_HOLD_DAYS = 30
KILL_SWITCH = False

# ── Bitget Demo ──────────────────────────────────────────
BITGET_API_KEY = os.getenv("BITGET_API_KEY", "")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET", "")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE", "")
BITGET_PRODUCT_TYPE = "USDT-FUTURES"
BITGET_MARGIN_COIN = "USDT"

# ── Compat (legacy) ─────────────────────────────────────
OKX_SYMBOL_MAP = {"BTCUSDT": "BTCUSDT", "ETHUSDT": "ETHUSDT"}
OKX_CONTRACT_SIZE = {"BTCUSDT": 0.0001, "ETHUSDT": 0.01}

# ── Risk ────────────────────────────────────────────────
ACCOUNT_EQUITY_USDT = 10000.0
RISK_PER_TRADE_PCT = 1.0
DAILY_LOSS_LIMIT_PCT = 3.0
MAX_OPEN_POSITIONS = 1
ATR_STOP_MULTIPLIER = 2.0
ATR_TP_MULTIPLIER = 6.0

# ── Objectif de test ────────────────────────────────────
TARGET_CAPITAL = 100000.0

# ── Data APIs ───────────────────────────────────────────
FEAR_GREED_API = "https://api.alternative.me/fng/"
CRYPTOCOMPARE_API = "https://min-api.cryptocompare.com/data"
CRYPTOCOMPARE_API_KEY = os.getenv("CRYPTOCOMPARE_API_KEY", "")

# ── Audit ───────────────────────────────────────────────
LOG_DIR = "logs"
AUDIT_DB = "logs/audit.db"

# ── Telegram ────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── LLM (legacy) ────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "openai/gpt-oss-120b"

# ── Mode de fonctionnement ──────────────────────────────
DRY_RUN = False
