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
    )

    def __init__(self):
        self.atr = bt.ind.ATR(self.data, period=self.p.atr_period)
        self.hh = bt.ind.Highest(self.data.high, period=self.p.lookback)
        self.ll = bt.ind.Lowest(self.data.low, period=self.p.lookback)

        self.order = None
        self.sl = None
        self.tp = None
        self.pending_reason = ""
        self.trades = []
        self._open = None

    def _size_by_risk(self, entry, sl):
        equity = self.broker.getvalue()
        risk_cash = equity * self.p.risk_pct
        rpu = abs(entry - sl)
        if rpu <= 0:
            return 0.0
        return risk_cash / rpu

    def next(self):
        if self.order:
            return

        c = float(self.data.close[0])
        atr = float(self.atr[0])

        if not self.position:
            # avoid lookahead: use previous bar highest/lowest
            if c > float(self.hh[-1]):
                entry = c
                self.sl = entry - atr * self.p.atr_mult_sl
                risk = abs(entry - self.sl)
                self.tp = entry + risk * self.p.rr
                size = self._size_by_risk(entry, self.sl)
                if size > 0:
                    self.pending_reason = f"LONG breakout > HH({self.p.lookback})"
                    self.order = self.buy(size=size)

            elif c < float(self.ll[-1]):
                entry = c
                self.sl = entry + atr * self.p.atr_mult_sl
                risk = abs(entry - self.sl)
                self.tp = entry - risk * self.p.rr
                size = self._size_by_risk(entry, self.sl)
                if size > 0:
                    self.pending_reason = f"SHORT breakout < LL({self.p.lookback})"
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

        dt = self.data.datetime.datetime(0)

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

        dt = self.data.datetime.datetime(0)
        if self._open:
            self._open["exit_time"] = dt.isoformat(sep=" ")
            self._open["exit_price"] = float(self.data.close[0])  # marker convenience
            self._open["pnl"] = float(trade.pnl)
            self._open["pnlcomm"] = float(trade.pnlcomm)
            self.trades.append(self._open)
            self._open = None

def csv_to_candles_json(csv_path: Path):
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=False)
    df["time"] = (df["datetime"].view("int64") // 10**9).astype(int)
    candles = df[["time", "open", "high", "low", "close"]].to_dict(orient="records")
    return candles

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

    candles = csv_to_candles_json(csv_path)
    (out_dir / "candles.json").write_text(json.dumps(candles, ensure_ascii=False), encoding="utf-8")

    cerebro = bt.Cerebro(stdstats=False)
    data = bt.feeds.GenericCSVData(
        dataname=str(csv_path),
        dtformat="%Y-%m-%d %H:%M:%S",
        datetime=0, open=1, high=2, low=3, close=4, volume=5,
        openinterest=-1,
        timeframe=bt.TimeFrame.Minutes,
        compression=5,
        header=0,
    )
    cerebro.adddata(data)
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

if __name__ == "__main__":
    main()
