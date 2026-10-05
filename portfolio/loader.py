"""CSV parsing and validation for transaction files."""
import pandas as pd

COLUMNS = ["ticker", "date", "type", "quantity", "price"]
_ALIASES = {"tickler": "ticker", "symbol": "ticker", "transaction_type": "type",
            "qty": "quantity"}


def normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Return a clean transactions frame plus warnings for dropped rows."""
    warnings: list[str] = []
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
    df = df.rename(columns=lambda c: _ALIASES.get(str(c).strip().lower(),
                                                  str(c).strip().lower()))
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}")
    df = df[COLUMNS].dropna(how="all").copy()
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["type"] = df["type"].astype(str).str.strip().str.upper()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    bad = (df["date"].isna() | ~df["type"].isin(["BUY", "SELL"])
           | ~(df["quantity"] > 0) | ~(df["price"] > 0) | (df["ticker"] == ""))
    if bad.any():
        warnings.append(f"Dropped {int(bad.sum())} invalid row(s) "
                        f"(bad date/type/quantity/price): "
                        f"{', '.join(df.loc[bad, 'ticker'].astype(str))}")
    return df[~bad].reset_index(drop=True), warnings


def parse_csv(file) -> tuple[pd.DataFrame, list[str]]:
    return normalize(pd.read_csv(file))
