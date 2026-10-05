from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from portfolio import engine, loader, metrics, prices

st.set_page_config(page_title="Portfolio Analyzer", layout="wide")
st.title("Portfolio Analyzer")

if "tx" not in st.session_state:
    st.session_state.tx = pd.DataFrame(columns=loader.COLUMNS)
if "uploaded_sig" not in st.session_state:
    st.session_state.uploaded_sig = None

tab1, tab2, tab3 = st.tabs(["Input Transactions", "Current Portfolio",
                            "Historical Performance"])


def money(x: float) -> str:
    return f"${x:,.2f}"


@st.cache_data(show_spinner="Fetching prices…")
def analyze(tx: pd.DataFrame):
    holdings, applied, warns = engine.replay(tx)
    px_now = prices.latest_prices(tuple(holdings.ticker))
    holdings["price"] = holdings.ticker.map(px_now)
    holdings["market_value"] = holdings.quantity * holdings.price
    holdings["unrealized"] = holdings.market_value - holdings.quantity * holdings.avg_cost
    holdings["unrealized_pct"] = holdings.price / holdings.avg_cost - 1
    return holdings, applied, warns


# ---------------------------------------------------------------- Tab 1
with tab1:
    st.subheader("Input Transactions")
    left, right = st.columns(2)

    with left:
        st.markdown("**CSV Upload**")
        f = st.file_uploader("Columns: ticker, date, type (BUY/SELL), quantity, price",
                             type="csv")
        if f is not None:
            sig = (f.name, f.size)
            if sig != st.session_state.uploaded_sig:
                try:
                    df, warns = loader.parse_csv(f)
                    st.session_state.tx = pd.concat([st.session_state.tx, df],
                                                    ignore_index=True)
                    st.session_state.uploaded_sig = sig
                    st.session_state.upload_warns = warns
                except Exception as e:
                    st.error(f"Could not read file: {e}")
        for w in st.session_state.get("upload_warns", []):
            st.warning(w)

    with right:
        st.markdown("**Manual Entry**")
        with st.form("add_tx", clear_on_submit=True):
            c1, c2 = st.columns(2)
            ticker = c1.text_input("Ticker")
            typ = c2.selectbox("Type", ["BUY", "SELL"])
            d = c1.date_input("Date")
            q = c2.number_input("Quantity", min_value=0.0, step=1.0)
            p = c1.number_input("Price", min_value=0.0, step=0.01)
            if st.form_submit_button("Add transaction"):
                row = pd.DataFrame([{"ticker": ticker, "date": d, "type": typ,
                                     "quantity": q, "price": p}])
                clean, w = loader.normalize(row)
                if clean.empty:
                    st.error(w[0] if w else "Invalid transaction.")
                else:
                    st.session_state.tx = pd.concat([st.session_state.tx, clean],
                                                    ignore_index=True)
                    st.rerun()

    st.markdown("**Transactions** — select rows via the checkbox and press Delete to remove.")
    if st.session_state.tx.empty:
        st.info("No transactions yet. Upload a CSV or add one manually.")
    else:
        edited = st.data_editor(
            engine.sort_transactions(st.session_state.tx), num_rows="dynamic",
            width="stretch", hide_index=True, key="editor",
            column_config={"date": st.column_config.DateColumn(),
                           "type": st.column_config.SelectboxColumn(options=["BUY", "SELL"])})
        clean, _ = loader.normalize(edited)
        if not clean.equals(st.session_state.tx):
            st.session_state.tx = clean
            st.rerun()
        st.download_button("Download CSV", st.session_state.tx.to_csv(index=False),
                           "transactions.csv", "text/csv")
        _, _, order_warns = engine.replay(st.session_state.tx)
        for w in order_warns:
            st.warning(w)

tx = st.session_state.tx
empty_msg = "Add transactions in the first tab to see this view."

# ---------------------------------------------------------------- Tab 2
with tab2:
    st.subheader("Current Portfolio")
    if tx.empty:
        st.info(empty_msg)
    else:
        holdings, applied, _ = analyze(tx)
        if holdings.empty:
            st.info("No open positions.")
        else:
            missing = holdings[holdings.price.isna()].ticker.tolist()
            if missing:
                st.warning(f"Price unavailable for: {', '.join(missing)} "
                           "(possibly delisted). Excluded from value totals.")
            priced = holdings.dropna(subset=["price"])
            st.metric("Current Value", money(priced.market_value.sum()))
            if not priced.empty:
                fig = px.pie(priced, names="ticker", values="market_value", hole=0.45)
                fig.update_traces(textinfo="label+percent")
                st.plotly_chart(fig, width="stretch")
            st.markdown("**Current Holdings**")
            show = holdings.rename(columns={
                "ticker": "Ticker", "quantity": "Quantity", "avg_cost": "Avg Cost",
                "price": "Current Price", "market_value": "Market Value",
                "unrealized": "Gain/Loss ($)", "unrealized_pct": "Gain/Loss (%)"})
            st.dataframe(
                show[["Ticker", "Quantity", "Avg Cost", "Current Price", "Market Value",
                      "Gain/Loss ($)", "Gain/Loss (%)"]],
                hide_index=True, width="stretch",
                column_config={
                    "Quantity": st.column_config.NumberColumn(format="%.4g"),
                    "Avg Cost": st.column_config.NumberColumn(format="$%.2f"),
                    "Current Price": st.column_config.NumberColumn(format="$%.2f"),
                    "Market Value": st.column_config.NumberColumn(format="$%.2f"),
                    "Gain/Loss ($)": st.column_config.NumberColumn(format="$%.2f"),
                    "Gain/Loss (%)": st.column_config.NumberColumn(format="percent")})

# ---------------------------------------------------------------- Tab 3
with tab3:
    st.subheader("Historical Performance")
    if tx.empty:
        st.info(empty_msg)
    else:
        holdings, applied, _ = analyze(tx)
        cur = float(holdings.market_value.sum(skipna=True)) if not holdings.empty else 0.0
        m = metrics.summary(tx, applied, cur, datetime.now())
        c = st.columns(3)
        c[0].metric("Total Invested", money(m["invested"]))
        c[1].metric("Total Sold", money(m["sold"]))
        c[2].metric("Current Value", money(m["current_value"]))
        c = st.columns(3)
        c[0].metric("Lifetime Proceeds", money(m["proceeds"]))
        pct = m["total_return_pct"]
        c[1].metric("Total Return", money(m["total_return"]),
                    f"{pct:.1%}" if pct is not None else None)
        c[2].metric("XIRR", f"{m['xirr']:.1%}" if m["xirr"] is not None else "n/a")
        if (tx.type == "SELL").any() and len(tx) != len(applied):
            st.caption("Total Sold includes SELLs skipped for missing positions; "
                       "XIRR and the trend line exclude them.")

        if not applied.empty:
            tickers = tuple(sorted(applied.ticker.unique()))
            closes = prices.history(tickers, applied.date.min().strftime("%Y-%m-%d"))
            series = metrics.value_series(applied, closes)
            if series.empty:
                st.warning("Historical prices unavailable; cannot draw trend.")
            else:
                st.markdown("**Portfolio Value Over Time**")
                trend = series.rename("Portfolio Value").rename_axis("Date").reset_index()
                fig = px.line(trend, x="Date", y="Portfolio Value")
                st.plotly_chart(fig, width="stretch")
