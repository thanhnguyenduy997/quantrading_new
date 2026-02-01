import json
import pandas as pd
import numpy as np

TRADES = "out/trades.json"
INIT_CAPITAL = 10_000

def main():
    df = pd.read_json(TRADES)

    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])

    df["pnl"] = df["pnlcomm"].fillna(df["pnl"])
    df["R"] = df["pnl"] / abs(df["pnl"].min())

    total_trades = len(df)
    win = df[df["pnl"] > 0]
    loss = df[df["pnl"] < 0]

    expectancy = (
        len(win)/total_trades * win["R"].mean()
        - len(loss)/total_trades * abs(loss["R"].mean())
    )

    equity = INIT_CAPITAL + df["pnl"].cumsum()
    peak = equity.cummax()
    dd = (equity - peak) / peak

    report = {
        "Total Trades": total_trades,
        "Net PnL": round(df["pnl"].sum(), 2),
        "Winrate (%)": round(len(win)/total_trades*100, 2),
        "Avg Win": round(win["pnl"].mean(), 2),
        "Avg Loss": round(loss["pnl"].mean(), 2),
        "Profit Factor": round(win["pnl"].sum()/abs(loss["pnl"].sum()), 2),
        "Expectancy (R)": round(expectancy, 3),
        "Max Drawdown (%)": round(dd.min()*100, 2),
    }

    print("\n=== QUANT SUMMARY ===")
    for k, v in report.items():
        print(f"{k:<20}: {v}")

if __name__ == "__main__":
    main()
