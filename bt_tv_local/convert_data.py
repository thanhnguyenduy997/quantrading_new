import pandas as pd
from pathlib import Path

SRC = Path("data/XAUUSD_5m_5Yea.csv")   # đổi đúng tên file của bạn
DST = Path("data/xauusd_m5.csv")

def main():
    df = pd.read_csv(SRC)

    # Normalize column names (strip spaces)
    df.columns = [c.strip() for c in df.columns]

    # Expect: Date, Time, Open, High, Low, Close, Volume
    # Date may be int like 20200821; Time like 00:00:00
    df["Date"] = df["Date"].astype(str).str.zfill(8)
    dt = pd.to_datetime(df["Date"] + " " + df["Time"], format="%Y%m%d %H:%M:%S", errors="coerce")

    bad = dt.isna().sum()
    if bad:
        raise ValueError(f"Datetime parse failed for {bad} rows. Check Date/Time format.")

    out = pd.DataFrame({
        "datetime": dt.dt.strftime("%Y-%m-%d %H:%M:%S"),
        "open": df["Open"],
        "high": df["High"],
        "low": df["Low"],
        "close": df["Close"],
        "volume": df["Volume"],
    })

    out.to_csv(DST, index=False)
    print(f"✅ Wrote: {DST} rows={len(out):,}")

if __name__ == "__main__":
    main()
