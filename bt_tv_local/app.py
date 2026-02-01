import json
from pathlib import Path
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
from quant.metrics import load_trades, summary
import pandas as pd
from quant.metrics import load_trades, summary
import pandas as pd
from quant.metrics import load_trades, summary, pnl_by_year, pnl_by_month, pnl_by_side

st.set_page_config(page_title="Backtrader Chart (Local)", layout="wide")
st.title("Backtrader + Streamlit + Lightweight Charts (Localhost)")
tabs = st.tabs(["📈 Chart", "📊 Quant Report"])

out_dir = Path("out")
candles_path = out_dir / "candles.json"
markers_path = out_dir / "markers.json"

with st.sidebar:
    st.header("How to run")
    st.code("python make_demo_data.py\npython run_backtest_export.py\nstreamlit run app.py", language="bash")
    st.divider()
    show_markers = st.checkbox("Show Entry/Exit Markers", value=True)
    height = st.slider("Height", 400, 900, 650, 50)

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

if not candles_path.exists():
    st.error("Missing out/candles.json. Run: python run_backtest_export.py")
    st.stop()

candles = load_json(candles_path)
markers = load_json(markers_path) if (show_markers and markers_path.exists()) else []

chart = {
    "height": height,
    "layout": {"background": {"type": "solid", "color": "#FFFFFF"}, "textColor": "#111827"},
    "grid": {"vertLines": {"color": "#E5E7EB"}, "horzLines": {"color": "#E5E7EB"}},
    "timeScale": {"timeVisible": True, "secondsVisible": False},
}

series = [{
    "type": "Candlestick",
    "data": candles,
    "options": {"upColor": "#22C55E", "downColor": "#EF4444", "borderVisible": False, "wickUpColor": "#22C55E", "wickDownColor": "#EF4444"},
}]

if show_markers and markers:
    series[0]["markers"] = markers

with tabs[0]:
    renderLightweightCharts([{"chart": chart, "series": series}])

    st.subheader("Quick checks")
    c1, c2 = st.columns(2)
    c1.metric("Candles", f"{len(candles):,}")
    c2.metric("Markers", f"{len(markers):,}" if show_markers else "0")

    with st.expander("markers sample"):
        st.json(markers[:8])

with tabs[1]:
    st.header("📊 Quant Report")

    df = load_trades("out/trades.json", init_capital=10_000)
    stats = summary(df)

    st.subheader("Summary")
    cols = st.columns(4)
    for i, (k, v) in enumerate(stats.items()):
        cols[i % 4].metric(k, v)

    st.divider()

    # ====== PHẦN B: BREAKDOWN ======
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




