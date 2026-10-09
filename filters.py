"""Regime / session / volatility / news filters."""
import ta
from datetime import datetime
from pathlib import Path

NEWS_FILE = Path("news_blackout.txt")
BLACKOUT_WINDOW_MIN = 30


def detect_regime(df):
    if len(df) < 60:
        return "unknown"
    d = df.copy()
    d["adx"] = ta.trend.ADXIndicator(d["high"], d["low"], d["close"], 14).adx()
    d["ema50"] = ta.trend.EMAIndicator(d["close"], 50).ema_indicator()
    d["ema200"] = ta.trend.EMAIndicator(d["close"], 200).ema_indicator()
    d = d.dropna()
    if len(d) < 2:
        return "unknown"
    last = d.iloc[-1]
    if last.adx >= 25 and abs(last.ema50 - last.ema200) / last.ema200 > 0.01:
        return "trending"
    if last.adx <= 18:
        return "ranging"
    return "unknown"


def is_weekend():
    return datetime.utcnow().weekday() >= 5


def is_us_session():
    h = datetime.utcnow().hour
    return 13 <= h < 20


def volatility_percentile(df, lookback=90):
    if len(df) < lookback + 20:
        return 50
    d = df.copy()
    d["atr"] = ta.volatility.AverageTrueRange(
        d["high"], d["low"], d["close"], 14
    ).average_true_range()
    d = d.dropna(subset=["atr"])
    if len(d) < lookback:
        return 50
    recent = d["atr"].iloc[-1]
    hist = d["atr"].iloc[-lookback:]
    return float((hist < recent).sum() / len(hist) * 100)


def in_news_blackout(now=None):
    if now is None:
        now = datetime.utcnow()
    if not NEWS_FILE.exists():
        return False
    for line in NEWS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            event = datetime.strptime(line, "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        delta = abs((now - event).total_seconds()) / 60
        if delta <= BLACKOUT_WINDOW_MIN:
            return True
    return False


def next_news_event():
    if not NEWS_FILE.exists():
        return None
    now = datetime.utcnow()
    events = []
    for line in NEWS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            events.append(datetime.strptime(line, "%Y-%m-%d %H:%M"))
        except ValueError:
            continue
    future = [e for e in events if e > now]
    return min(future) if future else None
