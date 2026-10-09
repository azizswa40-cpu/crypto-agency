import os
from dotenv import load_dotenv
load_dotenv()

# ============================================================
# MODE SÉCURISÉ — Aucun trade automatique
# ============================================================
DRY_RUN = True
SIGNAL_ONLY_MODE = True
FORCE_TEST_TRADE = False      # DÉSACTIVÉ — c'était le bug principal

# ============================================================
# STRATÉGIE
# ============================================================
STRATEGY_SYMBOLS = []
STRATEGY_INTERVAL = "1D"
CANDLE_LIMIT = 400
EMA_FAST = 50
EMA_SLOW = 200
ADX_MIN = 22
MAX_HOLD_DAYS = 30

# ============================================================
# LIMITES DE SÉCURITÉ STRICTES
# ============================================================
MAX_LEVERAGE = 1               # Pas de levier
MAX_OPEN_POSITIONS = 1         # 1 seule position à la fois
MAX_DAILY_TRADES = 1           # 1 trade max par jour
MAX_DAILY_LOSS_PCT = 1.0       # Stop si -1% dans la journée
COOLDOWN_HOURS = 24            # 24h minimum entre deux trades

# ============================================================
# RISK
# ============================================================
ACCOUNT_EQUITY_USDT = 500.0    # Réaliste par rapport au solde actuel
RISK_PER_TRADE_PCT = 0.5       # 0.5% par trade (très conservateur)
DAILY_LOSS_LIMIT_PCT = 1.0
ATR_STOP_MULTIPLIER = 2.0
ATR_TP_MULTIPLIER = 6.0

# ============================================================
# Bitget Demo
# ============================================================
BITGET_API_KEY = os.getenv("BITGET_API_KEY", "")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET", "")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE", "")
BITGET_PRODUCT_TYPE = "USDT-FUTURES"
BITGET_MARGIN_COIN = "USDT"

# ============================================================
# Compat legacy
# ============================================================
OKX_SYMBOL_MAP = {"BTCUSDT": "BTCUSDT", "ETHUSDT": "ETHUSDT", "SOLUSDT": "SOLUSDT"}
OKX_CONTRACT_SIZE = {"BTCUSDT": 0.0001, "ETHUSDT": 0.01, "SOLUSDT": 1.0}

# ============================================================
# Objectif symbolique
# ============================================================
TARGET_CAPITAL = 100000.0

# ============================================================
# APIs
# ============================================================
FEAR_GREED_API = "https://api.alternative.me/fng/"
CRYPTOCOMPARE_API = "https://min-api.cryptocompare.com/data"
CRYPTOCOMPARE_API_KEY = os.getenv("CRYPTOCOMPARE_API_KEY", "")

# ============================================================
# Audit
# ============================================================
LOG_DIR = "logs"
AUDIT_DB = "logs/audit.db"

# ============================================================
# Telegram
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================
# LLM
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "openai/gpt-oss-120b"
