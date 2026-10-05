"""yfinance wrappers. Failures return empty/NaN rather than raising."""
import pandas as pd
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=900, show_spinner=False)
def latest_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    """Last close per ticker; tickers that can't be resolved are omitted."""
    out: dict[str, float] = {}
    if not tickers:
        return out
    try:
        data = yf.download(list(tickers), period="10d", auto_adjust=True,
                           progress=False)["Close"]
    except Exception:
        return out
    if isinstance(data, pd.Series):
        data = data.to_frame(tickers[0])
    for t in data.columns:
        s = data[t].dropna()
        if not s.empty:
            out[t] = float(s.iloc[-1])
    return out


@st.cache_data(ttl=900, show_spinner=False)
def history(tickers: tuple[str, ...], start: str) -> pd.DataFrame:
    """Daily closes (columns = tickers), forward-filled; empty on failure."""
    if not tickers:
        return pd.DataFrame()
    try:
        data = yf.download(list(tickers), start=start, auto_adjust=True,
                           progress=False)["Close"]
    except Exception:
        return pd.DataFrame()
    if isinstance(data, pd.Series):
        data = data.to_frame(tickers[0])
    return data.dropna(how="all").ffill()
