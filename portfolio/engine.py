"""Holdings replay using average-cost basis."""
import pandas as pd


def sort_transactions(tx: pd.DataFrame) -> pd.DataFrame:
    """Chronological order; BUY before SELL on the same day."""
    order = tx["type"].map({"BUY": 0, "SELL": 1})
    return (tx.assign(_o=order).sort_values(["date", "_o"], kind="stable")
              .drop(columns="_o").reset_index(drop=True))


def replay(tx: pd.DataFrame):
    """Replay transactions.

    Returns (holdings, applied, warnings) where `applied` is the transaction
    list actually applied (orphan sells removed, over-sells clipped) and
    holdings has columns ticker, quantity, avg_cost, realized_pnl.
    """
    qty: dict[str, float] = {}
    cost: dict[str, float] = {}  # avg cost per share
    realized: dict[str, float] = {}
    applied, warnings = [], []

    for r in sort_transactions(tx).itertuples():
        t, q, p = r.ticker, float(r.quantity), float(r.price)
        held = qty.get(t, 0.0)
        if r.type == "BUY":
            new = held + q
            cost[t] = (held * cost.get(t, 0.0) + q * p) / new
            qty[t] = new
        else:
            if held <= 0:
                warnings.append(f"SELL {q:g} {t} on {r.date:%Y-%m-%d} skipped: "
                                f"no shares held.")
                continue
            if q > held:
                warnings.append(f"SELL {q:g} {t} on {r.date:%Y-%m-%d} clipped "
                                f"to {held:g} shares held.")
                q = held
            realized[t] = realized.get(t, 0.0) + q * (p - cost[t])
            qty[t] = held - q
        applied.append((r.ticker, r.date, r.type, q, p))

    applied_df = pd.DataFrame(applied, columns=["ticker", "date", "type",
                                                "quantity", "price"])
    holdings = pd.DataFrame({
        "ticker": list(qty),
        "quantity": [qty[t] for t in qty],
        "avg_cost": [cost[t] for t in qty],
        "realized_pnl": [realized.get(t, 0.0) for t in qty],
    })
    return holdings[holdings["quantity"] > 1e-9].reset_index(drop=True), applied_df, warnings
