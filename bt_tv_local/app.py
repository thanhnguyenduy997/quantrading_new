import json
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

from quant.metrics import load_trades, summary, pnl_by_year, pnl_by_month, pnl_by_side

st.set_page_config(page_title="Backtrader Chart (Local)", layout="wide")
st.title("Backtrader + Streamlit + Lightweight Charts (Localhost)")

tabs = st.tabs(["📈 Chart", "📊 Quant Report"])

OUT_DIR = Path("out")

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

# ---------- Sidebar ----------
with st.sidebar:
    st.header("How to run")
    st.code(
        "python run_backtest_export.py\n"
        "streamlit run app.py --server.fileWatcherType=poll",
        language="bash",
    )
    st.divider()

    tf = st.selectbox("Timeframe", ["M5", "M15", "H1", "H4", "D1"], index=0)
    st.caption(f"Selected TF: {tf}")

    show_markers = st.checkbox("Show Entry/Exit Markers", value=True)
    height = st.slider("Height", 400, 900, 650, 50)

# ---------- Paths by TF ----------
tf_file = {
    "M5":  "candles_m5.json",
    "M15": "candles_m15.json",
    "H1":  "candles_h1.json",
    "H4":  "candles_h4.json",
    "D1":  "candles_d1.json",
}[tf]

candles_path = OUT_DIR / tf_file

# fallback nếu chưa export multi-TF
if not candles_path.exists():
    st.warning(f"Missing {candles_path.name}. Fallback to candles.json")
    candles_path = OUT_DIR / "candles.json"

markers_path = OUT_DIR / "markers.json"
overlay_h1_path = OUT_DIR / "overlay_h1_sma.json"

# ---------- Load data ----------
if not candles_path.exists():
    st.error("Missing candles file. Run: python run_backtest_export.py")
    st.stop()

candles = load_json(candles_path)

# markers: chỉ nên show khi M5/M15 để đỡ dày
markers = []
if show_markers and tf in ["M5", "M15"] and markers_path.exists():
    markers = load_json(markers_path)

# overlay H1 SMA: chỉ hợp lý khi chart <= H1
overlay_h1 = []
if tf in ["M5", "M15", "H1"] and overlay_h1_path.exists():
    overlay_h1 = load_json(overlay_h1_path)

# ---------- Chart tab ----------
with tabs[0]:
    chart = {
        "height": height,
        "layout": {"background": {"type": "solid", "color": "#FFFFFF"}, "textColor": "#111827"},
        "grid": {"vertLines": {"color": "#E5E7EB"}, "horzLines": {"color": "#E5E7EB"}},
        "timeScale": {"timeVisible": True, "secondsVisible": False},
    }

    series = [{
        "type": "Candlestick",
        "data": candles,
        "options": {
            "upColor": "#22C55E",
            "downColor": "#EF4444",
            "borderVisible": False,
            "wickUpColor": "#22C55E",
            "wickDownColor": "#EF4444",
        },
    }]

    if overlay_h1:
        series.append({
            "type": "Line",
            "data": overlay_h1,
            "options": {"lineWidth": 2},
        })

    if markers:
        series[0]["markers"] = markers

    renderLightweightCharts([{"chart": chart, "series": series}])

    st.subheader("Quick checks")
    c1, c2, c3 = st.columns(3)
    c1.metric("TF", tf)
    c2.metric("Candles", f"{len(candles):,}")
    c3.metric("Markers", f"{len(markers):,}" if markers else "0")

    with st.expander("Debug"):
        st.write("candles_path:", str(candles_path))
        st.write("overlay_h1 points:", len(overlay_h1))
        if overlay_h1:
            st.write("overlay_h1 sample:", overlay_h1[:3])

# ---------- Quant report tab ----------
with tabs[1]:
    st.header("📊 Quant Report")

    trades_path = OUT_DIR / "trades.json"
    if not trades_path.exists():
        st.error("Missing out/trades.json. Run: python run_backtest_export.py")
        st.stop()

    df = load_trades(str(trades_path), init_capital=10_000)
    stats = summary(df)

    st.subheader("Summary")
    cols = st.columns(4)
    for i, (k, v) in enumerate(stats.items()):
        cols[i % 4].metric(k, v)

    st.divider()

    st.subheader("Breakdown (Year / Month / Side)")

    by_year = pnl_by_year(df)
    by_month = pnl_by_month(df)
    by_side = pnl_by_side(df)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**PnL by Year**")
        st.bar_chart(by_year.set_index("year")["pnl"])
        st.dataframe(by_year, use_container_width=True)

    with c2:
        st.markdown("**PnL by Side (LONG/SHORT)**")
        st.bar_chart(by_side.set_index("side")["pnl"])
        st.dataframe(by_side, use_container_width=True)

    st.markdown("**PnL by Month**")
    st.bar_chart(by_month.set_index("month")["pnl"])
    st.dataframe(by_month, use_container_width=True)

    st.divider()
    st.subheader("Equity")
    st.line_chart(df.set_index("exit_time")["equity"])

    st.subheader("Drawdown")
    st.line_chart(df.set_index("exit_time")["dd"])
