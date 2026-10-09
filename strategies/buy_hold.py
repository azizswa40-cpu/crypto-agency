from .base import Strategy


class BuyHoldStrategy(Strategy):
    name = "Buy & Hold"
    description = "Allocate 100% capital, hold forever."

    def prepare(self, df):
        return df.copy()

    def generate_signal(self, df, i):
        if i == 1:
            return {"action": "BUY_ALL", "atr": None, "reason": "initial"}
        return {"action": "HOLD", "atr": None, "reason": "holding"}
