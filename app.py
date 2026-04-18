import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from ta.momentum import RSIIndicator

st.set_page_config(page_title="Stock Dashboard", layout="wide")

tickers = ["NVDA", "MSFT", "AMZN", "GOOGL", "SOUN", "RGTI", "PLUG"]

buckets = {
    "NVDA": "Long Term",
    "MSFT": "Long Term",
    "AMZN": "Long Term",
    "GOOGL": "Long Term",
    "SOUN": "Aggressive",
    "RGTI": "Aggressive",
    "PLUG": "Aggressive",
}

st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #081120 0%, #0f172a 100%);
}
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
h1, h2, h3, p, div, span, label {
    color: #e5e7eb !important;
}
.hero {
    background: linear-gradient(135deg, #0f172a 0%, #111827 60%, #1f2937 100%);
    border: 1px solid #334155;
    border-radius: 22px;
    padding: 26px;
    margin-bottom: 18px;
}
.metric-card {
    background: linear-gradient(180deg, #111827 0%, #0b1220 100%);
    border: 1px solid #263244;
    border-radius: 18px;
    padding: 18px;
    min-height: 110px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.18);
}
.metric-label {
    color: #94a3b8 !important;
    font-size: 14px;
    margin-bottom: 8px;
}
.metric-value {
    font-size: 40px;
    font-weight: 800;
    line-height: 1;
}
.card {
    background: linear-gradient(180deg, #111827 0%, #0b1220 100%);
    border: 1px solid #263244;
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.18);
}
.badge {
    display: inline-block;
    padding: 8px 12px;
    border-radius: 999px;
    color: white !important;
    font-weight: 800;
    font-size: 12px;
}
.small-note {
    color: #94a3b8 !important;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)


def signal_color(signal):
    return {
        "BUY": "#16a34a",
        "HOLD": "#2563eb",
        "WAIT": "#f59e0b",
        "ERROR": "#dc2626"
    }.get(signal, "#64748b")


def get_data(ticker):
    df = yf.download(ticker, period="6mo", interval="1d", auto_adjust=True, progress=False)

    if df.empty:
        return None

    if "Close" not in df.columns:
        return None

    close = df["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close = pd.to_numeric(close, errors="coerce")

    clean = pd.DataFrame(index=df.index)
    clean["close"] = close
    clean["rsi"] = RSIIndicator(close=close).rsi()
    clean["ma20"] = close.rolling(20).mean()
    clean["ma50"] = close.rolling(50).mean()

    valid = clean.dropna(subset=["close", "rsi", "ma20", "ma50"])
    if valid.empty:
        return None

    return clean


def score_signal(df):
    valid = df.dropna(subset=["close", "rsi", "ma20", "ma50"])
    latest = valid.iloc[-1]

    close = float(latest["close"])
    ma20 = float(latest["ma20"])
    ma50 = float(latest["ma50"])
    rsi = float(latest["rsi"])

    score = 0
    reasons = []

    if close > ma20:
        score += 25
        reasons.append("Above MA20")
    else:
        reasons.append("Below MA20")

    if ma20 > ma50:
        score += 25
        reasons.append("MA20 above MA50")
    else:
        reasons.append("MA20 below MA50")

    if 45 <= rsi <= 68:
        score += 25
        reasons.append("RSI healthy")
    elif rsi < 45:
        score += 15
        reasons.append("RSI cooled off")
    else:
        reasons.append("RSI high")

    gap = ((close / ma20) - 1) * 100

    if -2 <= gap <= 5:
        score += 25
        reasons.append("Good entry distance")
    elif gap < -2:
        score += 10
        reasons.append("Below short trend")
    else:
        reasons.append("Overextended")

    if close > ma20 and ma20 > ma50 and rsi < 70 and gap <= 5:
        signal = "BUY"
    elif rsi > 75 or gap > 8:
        signal = "WAIT"
    else:
        signal = "HOLD"

    return signal, int(score), "; ".join(reasons)


def build_price_chart(df, ticker):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["close"], mode="lines", name="Close"))
    fig.add_trace(go.Scatter(x=df.index, y=df["ma20"], mode="lines", name="MA20"))
    fig.add_trace(go.Scatter(x=df.index, y=df["ma50"], mode="lines", name="MA50"))
    fig.update_layout(
        title=f"{ticker} Price Trend",
        template="plotly_white",
        height=360,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h")
    )
    return fig


def build_rsi_chart(df, ticker):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], mode="lines", name="RSI"))
    fig.add_hline(y=70, line_dash="dash")
    fig.add_hline(y=30, line_dash="dash")
    fig.update_layout(
        title=f"{ticker} RSI",
        template="plotly_white",
        height=260,
        margin=dict(l=20, r=20, t=50, b=20),
        showlegend=False
    )
    return fig


st.markdown("""
<div class="hero">
    <h1 style="margin:0 0 8px 0;font-size:48px;">Stock Dashboard</h1>
    <p style="margin:0;font-size:18px;color:#cbd5e1 !important;">
        Ranked setups, clean signals, and charts that actually look good.
    </p>
</div>
""", unsafe_allow_html=True)

results = []
data_map = {}

for ticker in tickers:
    df = get_data(ticker)

    if df is None:
        results.append({
            "Ticker": ticker,
            "Bucket": buckets.get(ticker, "Other"),
            "Price": None,
            "1D %": None,
            "RSI": None,
            "MA20": None,
            "MA50": None,
            "Signal": "ERROR",
            "Score": 0,
            "Reason": "Not enough valid data"
        })
        continue

    data_map[ticker] = df
    signal, score, reason = score_signal(df)

    valid = df.dropna(subset=["close", "rsi", "ma20", "ma50"])
    latest = valid.iloc[-1]

    close_series = df["close"].dropna()
    change_1d = ((close_series.iloc[-1] / close_series.iloc[-2]) - 1) * 100 if len(close_series) > 1 else 0.0

    results.append({
        "Ticker": ticker,
        "Bucket": buckets.get(ticker, "Other"),
        "Price": round(float(latest["close"]), 2),
        "1D %": round(change_1d, 2),
        "RSI": round(float(latest["rsi"]), 1),
        "MA20": round(float(latest["ma20"]), 2),
        "MA50": round(float(latest["ma50"]), 2),
        "Signal": signal,
        "Score": score,
        "Reason": reason
    })

df_results = pd.DataFrame(results).sort_values(by="Score", ascending=False).reset_index(drop=True)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Watchlist Size</div>
        <div class="metric-value">{len(df_results)}</div>
    </div>
    """, unsafe_allow_html=True)
with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">BUY Signals</div>
        <div class="metric-value">{len(df_results[df_results["Signal"] == "BUY"])}</div>
    </div>
    """, unsafe_allow_html=True)
with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">HOLD Signals</div>
        <div class="metric-value">{len(df_results[df_results["Signal"] == "HOLD"])}</div>
    </div>
    """, unsafe_allow_html=True)
with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">WAIT Signals</div>
        <div class="metric-value">{len(df_results[df_results["Signal"] == "WAIT"])}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("### Best Setups Right Now")
top3 = df_results.head(3)
c1, c2, c3 = st.columns(3)

for col, (_, row) in zip([c1, c2, c3], top3.iterrows()):
    with col:
        st.markdown(f"""
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-size:28px;font-weight:800;">{row['Ticker']}</div>
                    <div style="color:#94a3b8 !important;">{row['Bucket']}</div>
                </div>
                <div class="badge" style="background:{signal_color(row['Signal'])};">{row['Signal']}</div>
            </div>
            <div style="margin-top:12px;">Score: <b>{row['Score']}</b></div>
            <div style="margin-top:8px;color:#cbd5e1 !important;">{row['Reason']}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("### Ranked Watchlist")
st.dataframe(df_results, use_container_width=True, hide_index=True)

st.markdown("### Charts")
selected = st.selectbox("Choose a ticker", df_results["Ticker"].tolist())

if selected in data_map:
    row = df_results[df_results["Ticker"] == selected].iloc[0]
    df_sel = data_map[selected]

    left, right = st.columns([1, 2])

    with left:
        st.markdown(f"""
        <div class="card">
            <div style="font-size:34px;font-weight:800;">{selected}</div>
            <div style="color:#94a3b8 !important;margin-bottom:12px;">{row['Bucket']}</div>
            <div class="badge" style="background:{signal_color(row['Signal'])};">{row['Signal']}</div>
            <div style="margin-top:14px;">Price: <b>{row['Price']}</b></div>
            <div style="margin-top:8px;">1D %: <b>{row['1D %']}</b></div>
            <div style="margin-top:8px;">RSI: <b>{row['RSI']}</b></div>
            <div style="margin-top:8px;">MA20: <b>{row['MA20']}</b></div>
            <div style="margin-top:8px;">MA50: <b>{row['MA50']}</b></div>
            <div style="margin-top:12px;">Reason:</div>
            <div style="margin-top:6px;color:#cbd5e1 !important;">{row['Reason']}</div>
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.plotly_chart(build_price_chart(df_sel, selected), use_container_width=True)
        st.plotly_chart(build_rsi_chart(df_sel, selected), use_container_width=True)