import json
from pathlib import Path
import pandas as pd
import backtrader as bt

class ExportTradesStrategy(bt.Strategy):
    params = dict(
        lookback=20,
        atr_period=14,
        atr_mult_sl=2.0,
        rr=2.0,
        risk_pct=0.01,

        # --- MTF params ---
        h1_sma_period=200,   # filter trend on H1
    )

    def __init__(self):
        # === Multi-timeframe aliases (fixed mapping) ===
        # Because you add/resample in this order:
        # 0=M5, 1=M15, 2=H1, 3=H4, 4=D1
        self.m5 = self.datas[0]
        self.m15 = self.datas[1]
        self.h1 = self.datas[2]
        self.h4 = self.datas[3]
        self.d1 = self.datas[4]

        # === Indicators on M5 (entry timeframe) ===
        self.atr = bt.ind.ATR(self.m5, period=self.p.atr_period)
        self.hh = bt.ind.Highest(self.m5.high, period=self.p.lookback)
        self.ll = bt.ind.Lowest(self.m5.low, period=self.p.lookback)

        # === H1 trend filter ===
        self.h1_sma = bt.ind.SMA(self.h1.close, period=self.p.h1_sma_period)

        # === State ===
        self.order = None
        self.sl = None
        self.tp = None
        self.pending_reason = ""
        self.trades = []
        self._open = None

    def start(self):
        for i, d in enumerate(self.datas):
            print("DATA", i, "TF=", d._timeframe, "COMP=", d._compression)

    def _size_by_risk(self, entry, sl):
        equity = self.broker.getvalue()
        risk_cash = equity * self.p.risk_pct
        rpu = abs(entry - sl)
        if rpu <= 0:
            return 0.0
        return risk_cash / rpu

    def _h1_trend_ok(self):
        """
        Returns (trend_up, trend_dn).
        If no H1 feed provided, allow both directions (no filter).
        """
        if self.h1 is None or self.h1_sma is None:
            return True, True

        # Need enough H1 bars to compute SMA
        if len(self.h1) < self.p.h1_sma_period:
            return False, False

        trend_up = float(self.h1.close[0]) > float(self.h1_sma[0])
        trend_dn = float(self.h1.close[0]) < float(self.h1_sma[0])
        return trend_up, trend_dn

    def next(self):
        if self.order:
            return

        trend_up, trend_dn = self._h1_trend_ok()
        # If H1 exists but not ready yet, do nothing
        if self.h1 is not None and (not trend_up and not trend_dn):
            return

        c = float(self.m5.close[0])
        atr = float(self.atr[0])

        if not self.position:
            # avoid lookahead: use previous bar highest/lowest
            if trend_up and c > float(self.hh[-1]):
                entry = c
                self.sl = entry - atr * self.p.atr_mult_sl
                risk = abs(entry - self.sl)
                self.tp = entry + risk * self.p.rr
                size = self._size_by_risk(entry, self.sl)
                if size > 0:
                    self.pending_reason = f"LONG (H1 UP) breakout > HH({self.p.lookback})" if self.h1 is not None else f"LONG breakout > HH({self.p.lookback})"
                    self.order = self.buy(size=size)

            elif trend_dn and c < float(self.ll[-1]):
                entry = c
                self.sl = entry + atr * self.p.atr_mult_sl
                risk = abs(entry - self.sl)
                self.tp = entry - risk * self.p.rr
                size = self._size_by_risk(entry, self.sl)
                if size > 0:
                    self.pending_reason = f"SHORT (H1 DOWN) breakout < LL({self.p.lookback})" if self.h1 is not None else f"SHORT breakout < LL({self.p.lookback})"
                    self.order = self.sell(size=size)

        else:
            if self.position.size > 0:
                if c <= self.sl or c >= self.tp:
                    self.order = self.close()
            elif self.position.size < 0:
                if c >= self.sl or c <= self.tp:
                    self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        dt = self.m5.datetime.datetime(0)

        if order.status == order.Completed:
            if self._open is None:
                is_buy = order.isbuy()
                self._open = dict(
                    entry_time=dt.isoformat(sep=" "),
                    entry_price=float(order.executed.price),
                    size=float(order.executed.size),
                    side=("LONG" if is_buy else "SHORT"),
                    reason=self.pending_reason,
                    sl=float(self.sl) if self.sl is not None else None,
                    tp=float(self.tp) if self.tp is not None else None,
                    exit_time="",
                    exit_price=None,
                    pnl=None,
                    pnlcomm=None,
                )

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        dt = self.m5.datetime.datetime(0)
        if self._open:
            self._open["exit_time"] = dt.isoformat(sep=" ")
            self._open["exit_price"] = float(self.m5.close[0])  # marker convenience
            self._open["pnl"] = float(trade.pnl)
            self._open["pnlcomm"] = float(trade.pnlcomm)
            self.trades.append(self._open)
            self._open = None

def csv_to_candles_json(csv_path: Path):
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

    # convert datetime -> unix seconds (safe for pandas 2.x)
    df["time"] = (df["datetime"].astype("int64") // 10**9).astype("int64")

    candles = df[["time", "open", "high", "low", "close"]].to_dict(orient="records")
    return candles

def export_tf_candles(csv_path: Path, out_dir: Path):
    df = pd.read_csv(csv_path)

    # bạn đang dùng datetime cột tên "datetime"
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])

    def to_candles(dfx: pd.DataFrame):
        dfx = dfx.dropna(subset=["open", "high", "low", "close"])
        dfx["time"] = (dfx["datetime"].astype("int64") // 10**9).astype("int64")
        return dfx[["time", "open", "high", "low", "close"]].to_dict("records")

    def resample_ohlc(rule: str):
        o = (
            df.resample(rule, on="datetime")
              .agg(open=("open", "first"),
                   high=("high", "max"),
                   low=("low", "min"),
                   close=("close", "last"))
              .dropna()
              .reset_index()
        )
        return o

    # M5 gốc
    (out_dir / "candles_m5.json").write_text(json.dumps(to_candles(df), ensure_ascii=False), encoding="utf-8")

    # Các TF lớn hơn (rule chữ thường cho pandas)
    (out_dir / "candles_m15.json").write_text(json.dumps(to_candles(resample_ohlc("15min")), ensure_ascii=False), encoding="utf-8")
    (out_dir / "candles_h1.json").write_text(json.dumps(to_candles(resample_ohlc("1h")), ensure_ascii=False), encoding="utf-8")
    (out_dir / "candles_h4.json").write_text(json.dumps(to_candles(resample_ohlc("4h")), ensure_ascii=False), encoding="utf-8")
    (out_dir / "candles_d1.json").write_text(json.dumps(to_candles(resample_ohlc("1d")), ensure_ascii=False), encoding="utf-8")

def trades_to_markers(trades):
    markers = []
    for t in trades:
        entry_time = pd.to_datetime(t["entry_time"])
        entry_ts = int(entry_time.value // 10**9)

        if t["side"] == "LONG":
            markers.append(dict(time=entry_ts, position="belowBar", shape="arrowUp", text=f"LONG\n{t.get('reason','')}"))
        else:
            markers.append(dict(time=entry_ts, position="aboveBar", shape="arrowDown", text=f"SHORT\n{t.get('reason','')}"))

        exit_time = pd.to_datetime(t["exit_time"])
        exit_ts = int(exit_time.value // 10**9)
        pnl = t.get("pnlcomm", t.get("pnl", 0.0))
        markers.append(dict(time=exit_ts, position=("aboveBar" if t["side"] == "LONG" else "belowBar"), shape="circle", text=f"EXIT\npnl={pnl:.2f}"))
    return markers

def main():
    csv_path = Path("data/xauusd_m5.csv")
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)
    export_tf_candles(csv_path, out_dir)

    candles = csv_to_candles_json(csv_path)
    (out_dir / "candles.json").write_text(json.dumps(candles, ensure_ascii=False), encoding="utf-8")

    export_h1_sma_overlay(csv_path, out_dir / "overlay_h1_sma.json", period=50)

    cerebro = bt.Cerebro(stdstats=False)

    data_m5 = bt.feeds.GenericCSVData(
        dataname=str(csv_path),
        dtformat="%Y-%m-%d %H:%M:%S",  # hoặc format bạn đã convert
        datetime=0, open=1, high=2, low=3, close=4, volume=5,
        openinterest=-1,
        timeframe=bt.TimeFrame.Minutes,
        compression=5,
        header=0,
    )

    # data0 = M5
    cerebro.adddata(data_m5)

    # data1 = M15
    cerebro.resampledata(data_m5, timeframe=bt.TimeFrame.Minutes, compression=15)

    # data2 = H1
    cerebro.resampledata(data_m5, timeframe=bt.TimeFrame.Minutes, compression=60)

    # data3 = H4
    cerebro.resampledata(data_m5, timeframe=bt.TimeFrame.Minutes, compression=240)

    # data4 = D1
    cerebro.resampledata(data_m5, timeframe=bt.TimeFrame.Days, compression=1)

    cerebro.broker.setcash(10_000)

    # simple FX/XAU cost model: approximate spread via fixed slippage
    spread = 0.20
    cerebro.broker.set_slippage_fixed(spread / 2.0, slip_open=True, slip_limit=True, slip_match=True, slip_out=False)

    cerebro.addstrategy(ExportTradesStrategy)
    results = cerebro.run()
    strat = results[0]

    trades = strat.trades
    (out_dir / "trades.json").write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")

    markers = trades_to_markers(trades)
    (out_dir / "markers.json").write_text(json.dumps(markers, ensure_ascii=False), encoding="utf-8")

    print("✅ Export done:")
    print(" - out/candles.json")
    print(" - out/trades.json")
    print(" - out/markers.json")
    print(f"End value: {cerebro.broker.getvalue():.2f}")

def export_h1_sma_overlay(csv_path: Path, out_path: Path, period=200):
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])

    # Resample M5 -> H1 OHLC
    h1 = (
        df.resample("1h", on="datetime")
          .agg(open=("open", "first"),
               high=("high", "max"),
               low=("low", "min"),
               close=("close", "last"))
          .dropna()
          .reset_index()
    )

    # H1 SMA on close
    h1["sma"] = h1["close"].rolling(period).mean()

    # LightweightCharts format: {time, value}
    h1["time"] = (h1["datetime"].astype("int64") // 10**9).astype("int64")

    overlay = h1.dropna(subset=["sma"])[["time", "sma"]].rename(columns={"sma": "value"}).to_dict("records")
    out_path.write_text(json.dumps(overlay, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    main()
