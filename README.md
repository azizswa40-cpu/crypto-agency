# Crypto Agency — Multi-Agent Trading System

Production-grade multi-agent system for crypto market analysis. Deployed on GitHub Actions, Render, and Streamlit Cloud.

**Status**: Trading part frozen — project is a technical showcase of AI agent orchestration and cloud engineering.

## What it demonstrates

- **11 AI agents**: 5 voting (Momentum, Trend, Liquidity, Funding, Mean Rev) + 4 analysts (Technical, Sentiment, OnChain, Fundamental) + CEO + Risk Manager
- **100% cloud**: no PC required (GitHub Actions + Render + Streamlit Cloud + UptimeRobot)
- **Financial data engineering**: Bitget REST API with HMAC-SHA256, paginated OHLCV, walk-forward backtesting
- **LLM integration**: Groq LLaMA 3.3 70B with live data context injection
- **Production concerns**: secrets management, structured logs, kill switches, news blackout

## Tech stack

Python 3.11 · Bitget API · Groq LLM · SQLite · Streamlit · Flask · scikit-learn · GitHub Actions · Render

## Key modules

| File | Purpose |
|---|---|
| `ensemble.py` | 5 agents + 4 analysts coordination |
| `filters.py` | Regime, volatility, news blackout |
| `backtest_v6.py` | Walk-forward ML backtest |
| `agents/risk_manager.py` | Hard-coded veto rules |
| `bot_server.py` | 24/7 Telegram bot with live context |
| `pages/1_Trading_Floor.py` | Streamlit visual dashboard |

## Honest results

Backtests on 400/800 daily BTC candles: **negative expectancy** across all configurations. 3 alternative strategies tested: no statistical edge found.

**Conclusion**: classic indicators do not beat the market. The value is the **engineering**, not the trading performance.

## What I learned

Multi-agent orchestration · HMAC-signed REST · Cloud deployment · LLM context injection · Walk-forward backtesting · Risk management as hard rules · Debugging distributed systems · The hard truth about algorithmic trading

## License

MIT
