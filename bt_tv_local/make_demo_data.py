import pandas as pd
import numpy as np
import os

def main():
    np.random.seed(7)
    idx = pd.date_range("2025-01-01", periods=10 * 24 * 12, freq="5min")  # 10 days M5
    price = 2000 + np.cumsum(np.random.normal(0, 0.6, size=len(idx)))

    close = price
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + np.abs(np.random.normal(0, 0.25, size=len(idx)))
    low = np.minimum(open_, close) - np.abs(np.random.normal(0, 0.25, size=len(idx)))
    vol = np.random.randint(50, 200, size=len(idx))

    df = pd.DataFrame({
        "datetime": idx.strftime("%Y-%m-%d %H:%M:%S"),
        "open": np.round(open_, 2),
        "high": np.round(high, 2),
        "low": np.round(low, 2),
        "close": np.round(close, 2),
        "volume": vol
    })

    os.makedirs("data", exist_ok=True)
    out = "data/xauusd_m5.csv"
    df.to_csv(out, index=False)
    print(f"OK -> wrote {out} ({len(df)} rows)")

if __name__ == "__main__":
    main()
