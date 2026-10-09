"""AI Trading Arena v3 — clean simulation, no sizing bugs."""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from datetime import datetime
from agents.market_data import MarketDataAgent
from strategies import (
    EmaAdxStrategy, MeanReversionStrategy, MomentumStrategy, BuyHoldStrategy,
)

FEE_RATE = 0.0006
INITIAL_EQUITY = 10000.0
SL_ATR = 2.0
TP_ATR = 6.0
POSITION_SIZE_PCT = 1.0  # 1% of equity as risk per trade for SL-based strategies


def simulate(strategy, df):
    d = strategy.prepare(df)
    is_bh = strategy.name == "Buy & Hold"

    equity = INITIAL_EQUITY
    curve = [equity]
    in_pos = False
    entry = sl = tp = None
    trades = []

    for i in range(1, len(d) - 1):
        row = d.iloc[i]
        nxt = d.iloc[i + 1]

        if in_pos and not is_bh:
            if nxt.low <= sl:
                ret_pct = (sl - entry) / entry
                equity *= (1 + ret_pct * POSITION_SIZE_PCT - FEE_RATE * 2)
                trades.append({"result": "loss", "ret": ret_pct})
                in_pos = False
            elif nxt.high >= tp:
                ret_pct = (tp - entry) / entry
                equity *= (1 + ret_pct * POSITION_SIZE_PCT - FEE_RATE * 2)
                trades.append({"result": "win", "ret": ret_pct})
                in_pos = False

        if not in_pos:
            sig = strategy.generate_signal(d, i)
            if sig["action"] in ("BUY", "BUY_ALL"):
                entry = row.close
                if sig["action"] == "BUY_ALL":
                    in_pos = True
                    sl = 0
                    tp = 999999999
                elif sig["atr"] and sig["atr"] > 0:
                    sl = entry - SL_ATR * sig["atr"]
                    tp = entry + TP_ATR * sig["atr"]
                    in_pos = True
            elif sig["action"] == "EXIT" and in_pos:
                ret_pct = (row.close - entry) / entry
                equity *= (1 + ret_pct * POSITION_SIZE_PCT - FEE_RATE * 2)
                trades.append({"result": "win" if ret_pct > 0 else "loss", "ret": ret_pct})
                in_pos = False

        curve.append(equity)

    if in_pos:
        exit_price = d.iloc[-1].close
        ret_pct = (exit_price - entry) / entry
        if is_bh:
            equity *= (1 + ret_pct - FEE_RATE * 2)
        else:
            equity *= (1 + ret_pct * POSITION_SIZE_PCT - FEE_RATE * 2)
        trades.append({"result": "win" if ret_pct > 0 else "loss", "ret": ret_pct})

    tdf = pd.DataFrame(trades) if trades else pd.DataFrame(columns=["result", "ret"])
    w = (tdf["result"] == "win").sum() if len(tdf) else 0
    l = (tdf["result"] == "loss").sum() if len(tdf) else 0
    total = w + l
    wr = w / total * 100 if total else 0
    aw = tdf.loc[tdf["result"] == "win", "ret"].mean() if w else 0
    al = tdf.loc[tdf["result"] == "loss", "ret"].mean() if l else 0
    gp = aw * w if w else 0
    gl = abs(al * l) if l else 0
    pf = gp / gl if gl else 0
    curve = np.array(curve)
    peak = np.maximum.accumulate(curve)
    dd = ((curve - peak) / peak).min() * 100 if len(curve) else 0
    ret = (equity - INITIAL_EQUITY) / INITIAL_EQUITY * 100
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    cagr = ((equity / INITIAL_EQUITY) ** (1 / yrs) - 1) * 100 if yrs > 0 and equity > 0 else 0

    return {
        "strategy": strategy.name, "trades": int(total), "wr": round(wr, 1),
        "pf": round(pf, 2), "equity": round(equity, 2),
        "ret_pct": round(ret, 1), "cagr": round(cagr, 1), "dd_pct": round(dd, 1),
    }


def run(symbol="BTCUSDT", days=1825):
    print(f"\n{'='*80}")
    print(f"  ARENA v3 — {symbol} — up to {days} days")
    print(f"{'='*80}\n")

    df = MarketDataAgent(symbol, interval="1D").fetch_candles()
    if df.empty:
        print("No data.")
        return
    df = df.tail(days)
    print(f"Data: {len(df)} candles | {df.index[0].date()} to {df.index[-1].date()}\n")

    strategies = [
        EmaAdxStrategy(adx_min=22),
        MeanReversionStrategy(),
        MomentumStrategy(),
        BuyHoldStrategy(),
    ]

    results = []
    for s in strategies:
        print(f"Running '{s.name}'...")
        results.append(simulate(s, df))

    results.sort(key=lambda x: x["equity"], reverse=True)

    print(f"\n{'='*80}")
    print(f"  RESULTS")
    print(f"{'='*80}\n")
    print(f"{'#':<3}{'Strategy':<22}{'Trades':<8}{'WR%':<8}{'PF':<7}{'Equity':<12}{'Return%':<10}{'CAGR%':<9}{'DD%':<8}")
    print("-" * 90)
    for i, r in enumerate(results, 1):
        print(f"{i:<3}{r['strategy']:<22}{r['trades']:<8}{r['wr']:<8}{r['pf']:<7}${r['equity']:<11}{r['ret_pct']:<10}{r['cagr']:<9}{r['dd_pct']:<8}")

    w = results[0]
    print(f"\n{'='*80}")
    print(f"  WINNER: {w['strategy']}")
    print(f"  ${w['equity']} | Return {w['ret_pct']:+.1f}% | CAGR {w['cagr']:+.1f}% | DD {w['dd_pct']:.1f}%")
    print(f"{'='*80}\n")

    pd.DataFrame(results).to_csv(
        f"logs/arena_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", index=False)


if __name__ == "__main__":
    run("BTCUSDT", 2000)
