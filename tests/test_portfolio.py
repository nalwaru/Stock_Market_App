import io
from datetime import datetime

import pandas as pd
import pytest

from portfolio import engine, loader, metrics

SAMPLE = """,Tickler,Date,Transaction_type,quantity,price,
1,AAPL,2026-01-05,BUY,10,185.07,
2,NVDA,2026-01-05,SELL,7,200.05,
3,NFLX,2026-04-08,BUY,20,300,
"""


def test_loader_handles_sample_format():
    df, warns = loader.parse_csv(io.StringIO(SAMPLE))
    assert list(df.columns) == loader.COLUMNS
    assert len(df) == 3 and not warns


def test_orphan_sell_skipped_with_warning():
    df, _ = loader.parse_csv(io.StringIO(SAMPLE))
    holdings, applied, warns = engine.replay(df)
    assert set(holdings.ticker) == {"AAPL", "NFLX"}
    assert len(applied) == 2 and any("NVDA" in w for w in warns)


def test_average_cost_and_realized():
    df = pd.DataFrame({"ticker": ["A"] * 3,
                       "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
                       "type": ["BUY", "BUY", "SELL"],
                       "quantity": [10, 10, 5], "price": [10.0, 20.0, 30.0]})
    h, _, _ = engine.replay(df)
    assert h.quantity[0] == 15 and h.avg_cost[0] == pytest.approx(15)
    assert h.realized_pnl[0] == pytest.approx(75)


def test_xirr_one_year_ten_percent():
    r = metrics.xirr([(datetime(2025, 1, 1), -100), (datetime(2026, 1, 1), 110)])
    assert r == pytest.approx(0.10, abs=1e-3)


def test_xirr_undefined_without_both_signs():
    assert metrics.xirr([(datetime(2025, 1, 1), -100), (datetime(2026, 1, 1), -5)]) is None
