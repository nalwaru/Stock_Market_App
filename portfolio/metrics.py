"""Portfolio-level metrics: totals, XIRR, daily value series."""
from datetime import datetime

import pandas as pd
from scipy.optimize import brentq


def xirr(flows: list[tuple[datetime, float]]) -> float | None:
    """Annualised IRR for dated cash flows; None if undefined."""
    if len(flows) < 2:
        return None
    amounts = [a for _, a in flows]
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return None
    t0 = min(d for d, _ in flows)

    def npv(rate: float) -> float:
        return sum(a / (1 + rate) ** ((d - t0).days / 365.0) for d, a in flows)

    try:
        return brentq(npv, -0.9999, 1e6)
    except ValueError:
        return None


def summary(raw_tx: pd.DataFrame, applied: pd.DataFrame, current_value: float,
            as_of: datetime) -> dict:
    """Headline metrics. Total sold uses all raw SELL rows (incl. orphans);
    XIRR uses only the applied transactions."""
    invested = float((raw_tx[raw_tx.type == "BUY"].eval("quantity * price")).sum())
    sold = float((raw_tx[raw_tx.type == "SELL"].eval("quantity * price")).sum())
    proceeds = sold + current_value
    ret = proceeds - invested
    flows = [(r.date.to_pydatetime(),
              -r.quantity * r.price if r.type == "BUY" else r.quantity * r.price)
             for r in applied.itertuples()]
    flows.append((as_of, current_value))
    return {"invested": invested, "sold": sold, "proceeds": proceeds,
            "current_value": current_value, "total_return": ret,
            "total_return_pct": ret / invested if invested else None,
            "xirr": xirr(flows)}


def value_series(applied: pd.DataFrame, closes: pd.DataFrame) -> pd.Series:
    """Daily portfolio value = sum(shares held * close)."""
    if applied.empty or closes.empty:
        return pd.Series(dtype=float)
    idx = closes.index
    signed = applied.assign(q=applied.quantity.where(applied.type == "BUY",
                                                     -applied.quantity))
    # transactions on non-trading days roll onto the next trading day
    daily = (signed.assign(d=signed.date.apply(
                 lambda d: idx[idx.searchsorted(d)] if d <= idx[-1] else idx[-1]))
             .pivot_table(index="d", columns="ticker", values="q", aggfunc="sum")
             .reindex(idx).fillna(0).reindex(columns=closes.columns, fill_value=0))
    held = daily.cumsum()
    return (held * closes.fillna(0)).sum(axis=1)
