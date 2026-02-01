import pandas as pd
import numpy as np

def load_trades(path="out/trades.json", init_capital=10_000):
    df = pd.read_json(path)

    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])

    # pnl chuẩn: ưu tiên pnlcomm, fallback pnl
    df["pnl"] = df["pnlcomm"].fillna(df["pnl"])

    # Equity + Drawdown (theo chuỗi trade)
    df["equity"] = init_capital + df["pnl"].cumsum()
    df["peak"] = df["equity"].cummax()
    df["dd"] = (df["equity"] - df["peak"]) / df["peak"]

    return df

def summary(df: pd.DataFrame):
    win = df[df["pnl"] > 0]
    loss = df[df["pnl"] < 0]

    profit_factor = (win["pnl"].sum() / abs(loss["pnl"].sum())) if len(loss) else np.inf

    return {
        "Total Trades": int(len(df)),
        "Winrate (%)": round(len(win) / len(df) * 100, 2) if len(df) else 0.0,
        "Net PnL": round(df["pnl"].sum(), 2),
        "Profit Factor": round(profit_factor, 2) if np.isfinite(profit_factor) else "inf",
        "Expectancy": round(df["pnl"].mean(), 2) if len(df) else 0.0,
        "Max Drawdown (%)": round(df["dd"].min() * 100, 2) if len(df) else 0.0,
    }

# =========================
# BREAKDOWN FUNCTIONS (PHẦN B)
# =========================

def pnl_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng PnL theo năm"""
    x = df.copy()
    x["year"] = x["exit_time"].dt.year
    out = x.groupby("year", as_index=False)["pnl"].sum()
    out = out.sort_values("year")
    return out

def pnl_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng PnL theo tháng (YYYY-MM)"""
    x = df.copy()
    x["month"] = x["exit_time"].dt.to_period("M").astype(str)  # '2024-08'
    out = x.groupby("month", as_index=False)["pnl"].sum()
    # sort theo thời gian
    out["month_dt"] = pd.to_datetime(out["month"] + "-01")
    out = out.sort_values("month_dt").drop(columns=["month_dt"])
    return out

def pnl_by_side(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng PnL theo LONG/SHORT"""
    x = df.copy()
    if "side" not in x.columns:
        # fallback: nếu bạn lưu direction tên khác
        if "direction" in x.columns:
            x["side"] = x["direction"]
        else:
            x["side"] = "UNKNOWN"

    out = x.groupby("side", as_index=False)["pnl"].sum()
    # sort theo giá trị pnl giảm dần cho dễ nhìn
    out = out.sort_values("pnl", ascending=False)
    return out
