"""Arena multi-symbol — tests all strategies on BTC, ETH, SOL."""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from datetime import datetime
from agents.market_data import MarketDataAgent
from strategies import (
    EmaAdxStrategy, MeanReversionStrategy, MomentumStrategy, BuyHoldStrategy,
)
from arena import simulate

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def run_symbol(symbol):
    print(f"\n{'='*80}")
    print(f"  {symbol}")
    print(f"{'='*80}")

    df = MarketDataAgent(symbol, interval="1D").fetch_candles()
    if df.empty or len(df) < 100:
        print(f"  Not enough data for {symbol}")
        return None

    df = df.tail(1500)
    print(f"  Data: {len(df)} candles | {df.index[0].date()} to {df.index[-1].date()}\n")

    strategies = [
        EmaAdxStrategy(adx_min=22),
        MeanReversionStrategy(),
        MomentumStrategy(),
        BuyHoldStrategy(),
    ]

    results = []
    for s in strategies:
        r = simulate(s, df)
        r["symbol"] = symbol
        results.append(r)

    results.sort(key=lambda x: x["equity"], reverse=True)

    print(f"  {'#':<3}{'Strategy':<22}{'Trades':<8}{'WR%':<8}{'PF':<7}{'Equity':<12}{'Return%':<10}{'CAGR%':<9}{'DD%':<8}")
    print("  " + "-" * 88)
    for i, r in enumerate(results, 1):
        print(f"  {i:<3}{r['strategy']:<22}{r['trades']:<8}{r['wr']:<8}{r['pf']:<7}${r['equity']:<11}{r['ret_pct']:<10}{r['cagr']:<9}{r['dd_pct']:<8}")

    return results


if __name__ == "__main__":
    print(f"\n{'='*80}")
    print(f"  MULTI-SYMBOL ARENA — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}")

    all_results = []
    for sym in SYMBOLS:
        r = run_symbol(sym)
        if r:
            all_results.extend(r)

    if all_results:
        pd.DataFrame(all_results).to_csv(
            f"logs/arena_multi_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            index=False)

        # Ranking by average return
        df = pd.DataFrame(all_results)
        summary = df.groupby("strategy").agg({
            "ret_pct": "mean",
            "cagr": "mean",
            "pf": "mean",
            "dd_pct": "mean",
        }).round(2).sort_values("ret_pct", ascending=False)

        print(f"\n{'='*80}")
        print(f"  AVG PERFORMANCE ACROSS {len(SYMBOLS)} SYMBOLS")
        print(f"{'='*80}\n")
        print(summary.to_string())
        print()
