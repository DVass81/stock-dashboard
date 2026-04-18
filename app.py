import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from urllib.parse import quote_plus

st.set_page_config(
    page_title="Trading Terminal",
    page_icon="📈",
    layout="wide"
)

TICKERS = ["NVDA", "MSFT", "AMZN", "GOOGL", "SOUN", "RGTI", "PLUG"]

BUCKETS = {
    "NVDA": "Long Term",
    "MSFT": "Long Term",
    "AMZN": "Long Term",
    "GOOGL": "Long Term",
    "SOUN": "Aggressive",
    "RGTI": "Aggressive",
    "PLUG": "Aggressive",
}

# ---------------------------
# STYLING
# ---------------------------
st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #06101f 0%, #0b1728 55%, #111827 100%);
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

h1, h2, h3, h4, p, div, span, label {
    color: #e5e7eb !important;
}

.hero {
    background: linear-gradient(135deg, #0f172a 0%, #111827 45%, #1e293b 100%);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 24px;
    padding: 26px 28px;
    box-shadow: 0 12px 30px rgba(0,0,0,0.24);
    margin-bottom: 18px;
}

.metric-card {
    background: linear-gradient(180deg, #101827 0%, #0a1220 100%);
    border: 1px solid rgba(100, 116, 139, 0.28);
    border-radius: 22px;
    padding: 18px;
    min-height: 118px;
    box-shadow: 0 10px 24px rgba(0,0,0,0.20);
}

.metric-label {
    color: #94a3b8 !important;
    font-size: 14px;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.metric-value {
    font-size: 40px;
    font-weight: 800;
    line-height: 1;
}

.section-card {
    background: linear-gradient(180deg, #101827 0%, #0a1220 100%);
    border: 1px solid rgba(100, 116, 139, 0.26);
    border-radius: 22px;
    padding: 18px;
    box-shadow: 0 10px 24px rgba(0,0,0,0.20);
}

.badge {
    display: inline-block;
    padding: 8px 12px;
    border-radius: 999px;
    color: white !important;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.04em;
}

.small-note {
    color: #94a3b8 !important;
    font-size: 13px;
}

.terminal-note {
    color: #cbd5e1 !important;
    font-size: 14px;
}

div[data-baseweb="select"] * {
    color: black !important;
}

div[data-baseweb="select"] {
    background: white !important;
    border-radius: 10px !important;
}

.stDataFrame, .stTable {
    border-radius: 16px !important;
    overflow: hidden !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a1220 0%, #0d1729 100%);
}

hr {
    border-color: rgba(148, 163, 184, 0.15) !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------
# HELPERS
# ---------------------------
def signal_color(signal):
    return {
        "BUY": "#16a34a",
        "HOLD": "#2563eb",
        "WAIT": "#f59e0b",
        "ERROR": "#dc2626"
    }.get(signal, "#64748b")


def action_message(signal, score):
    if signal == "BUY" and score >= 75:
        return "Strong setup. Worth serious review."
    if signal == "BUY":
        return "Constructive setup. Check entry."
    if signal == "HOLD":
        return "Neutral to positive. No rush."
    if signal == "WAIT":
        return "Too stretched or overheated."
    return "Needs review."


def yahoo_chart_url(ticker):
    return f"https://finance.yahoo.com/quote/{quote_plus(ticker)}/chart"


def yahoo_quote_url(ticker):
    return f"https://finance.yahoo.com/quote/{quote_plus(ticker)}"


def fidelity_trade_url():
    return "https://www.fidelity.com/trading/overview"


def fidelity_research_url():
    return "https://digital.fidelity.com/prgw/digital/research/src"


def get_data(ticker):
    df = yf.download(
        ticker,
        period="6mo",
        interval="1d",
        auto_adjust=True,
        progress=False
    )

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
    clean["high20"] = close.rolling(20).max()
    clean["low20"] = close.rolling(20).min()
    clean["change_1d"] = clean["close"].pct_change() * 100
    clean["change_5d"] = clean["close"].pct_change(5) * 100
    clean["distance_ma20"] = ((clean["close"] / clean["ma20"]) - 1) * 100

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
    gap = ((close / ma20) - 1) * 100

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

    return signal, int(score), "; ".join(reasons), gap


def build_price_chart(df, ticker):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df.index, y=df["close"],
        mode="lines", name="Close",
        line=dict(width=3)
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["ma20"],
        mode="lines", name="MA20",
        line=dict(width=2, dash="solid")
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["ma50"],
        mode="lines", name="MA50",
        line=dict(width=2, dash="dot")
    ))

    fig.update_layout(
        title=f"{ticker} Price Trend",
        template="plotly_white",
        height=380,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h")
    )
    return fig


def build_rsi_chart(df, ticker):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["rsi"],
        mode="lines", name="RSI",
        line=dict(width=3)
    ))
    fig.add_hline(y=70, line_dash="dash")
    fig.add_hline(y=30, line_dash="dash")

    fig.update_layout(
        title=f"{ticker} RSI",
        template="plotly_white",
        height=280,
        margin=dict(l=20, r=20, t=50, b=20),
        showlegend=False
    )
    return fig


def build_score_gauge(score, ticker):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"{ticker} Setup Score"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"thickness": 0.35},
            "steps": [
                {"range": [0, 35], "color": "#fee2e2"},
                {"range": [35, 65], "color": "#dbeafe"},
                {"range": [65, 100], "color": "#dcfce7"},
            ]
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    return fig


# ---------------------------
# SIDEBAR
# ---------------------------
st.sidebar.header("Dashboard Controls")
refresh_seconds = st.sidebar.slider("Auto refresh (seconds)", 60, 900, 300, 30)
show_only = st.sidebar.multiselect(
    "Filter signals",
    options=["BUY", "HOLD", "WAIT", "ERROR"],
    default=["BUY", "HOLD", "WAIT", "ERROR"]
)

st.markdown(f"""
<script>
setTimeout(function() {{
    window.location.reload();
}}, {refresh_seconds * 1000});
</script>
""", unsafe_allow_html=True)

# ---------------------------
# HEADER
# ---------------------------
st.markdown("""
<div class="hero">
    <h1 style="margin:0 0 8px 0;font-size:52px;">📈 Trading Terminal</h1>
    <p style="margin:0;font-size:18px;color:#cbd5e1 !important;">
        Ranked setups, cleaner signals, fast research links, charts, heat checks, and action buttons.
    </p>
</div>
""", unsafe_allow_html=True)

# ---------------------------
# DATA BUILD
# ---------------------------
results = []
data_map = {}

for ticker in TICKERS:
    df = get_data(ticker)

    if df is None:
        results.append({
            "Ticker": ticker,
            "Bucket": BUCKETS.get(ticker, "Other"),
            "Price": None,
            "1D %": None,
            "5D %": None,
            "RSI": None,
            "MA20": None,
            "MA50": None,
            "Gap %": None,
            "Signal": "ERROR",
            "Score": 0,
            "Reason": "Not enough valid data"
        })
        continue

    data_map[ticker] = df
    signal, score, reason, gap = score_signal(df)

    valid = df.dropna(subset=["close", "rsi", "ma20", "ma50"])
    latest = valid.iloc[-1]

    results.append({
        "Ticker": ticker,
        "Bucket": BUCKETS.get(ticker, "Other"),
        "Price": round(float(latest["close"]), 2),
        "1D %": round(float(latest["change_1d"]), 2),
        "5D %": round(float(latest["change_5d"]), 2),
        "RSI": round(float(latest["rsi"]), 1),
        "MA20": round(float(latest["ma20"]), 2),
        "MA50": round(float(latest["ma50"]), 2),
        "Gap %": round(float(gap), 2),
        "Signal": signal,
        "Score": score,
        "Reason": reason
    })

df_results = pd.DataFrame(results)
df_results = df_results[df_results["Signal"].isin(show_only)]
df_results = df_results.sort_values(by="Score", ascending=False).reset_index(drop=True)

# ---------------------------
# METRICS
# ---------------------------
m1, m2, m3, m4, m5 = st.columns(5)

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

best_score = int(df_results["Score"].max()) if not df_results.empty else 0
with m5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Top Score</div>
        <div class="metric-value">{best_score}</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------
# TOP CARDS
# ---------------------------
st.markdown("### Best Setups Right Now")
top3 = df_results.head(3)
c1, c2, c3 = st.columns(3)

for col, (_, row) in zip([c1, c2, c3], top3.iterrows()):
    with col:
        st.markdown(f"""
        <div class="section-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-size:30px;font-weight:800;">{row['Ticker']}</div>
                    <div style="color:#94a3b8 !important;">{row['Bucket']}</div>
                </div>
                <div class="badge" style="background:{signal_color(row['Signal'])};">
                    {row['Signal']}
                </div>
            </div>
            <div style="margin-top:12px;">Score: <b>{row['Score']}</b></div>
            <div style="margin-top:8px;">Price: <b>{row['Price']}</b></div>
            <div style="margin-top:8px;" class="terminal-note">{row['Reason']}</div>
        </div>
        """, unsafe_allow_html=True)

# ---------------------------
# TABLE
# ---------------------------
st.markdown("### Ranked Watchlist")
st.dataframe(
    df_results[["Ticker", "Bucket", "Price", "1D %", "5D %", "RSI", "MA20", "MA50", "Gap %", "Signal", "Score", "Reason"]],
    use_container_width=True,
    hide_index=True
)

# ---------------------------
# EXTRA INSIGHT CARDS
# ---------------------------
st.markdown("### Quick Market Read")
q1, q2, q3 = st.columns(3)

if not df_results.empty:
    strongest = df_results.iloc[0]["Ticker"]
    hottest = df_results.sort_values("1D %", ascending=False).iloc[0]["Ticker"]
    coolest = df_results.sort_values("RSI", ascending=True).iloc[0]["Ticker"] if df_results["RSI"].notna().any() else "N/A"
else:
    strongest = hottest = coolest = "N/A"

with q1:
    st.markdown(f"""
    <div class="section-card">
        <div class="metric-label">Strongest Setup</div>
        <div style="font-size:30px;font-weight:800;">{strongest}</div>
    </div>
    """, unsafe_allow_html=True)

with q2:
    st.markdown(f"""
    <div class="section-card">
        <div class="metric-label">Best 1-Day Move</div>
        <div style="font-size:30px;font-weight:800;">{hottest}</div>
    </div>
    """, unsafe_allow_html=True)

with q3:
    st.markdown(f"""
    <div class="section-card">
        <div class="metric-label">Most Cooled Off</div>
        <div style="font-size:30px;font-weight:800;">{coolest}</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------
# DETAIL PANEL
# ---------------------------
st.markdown("### Terminal Detail")
selected = st.selectbox("Choose a ticker", df_results["Ticker"].tolist())

if selected in data_map:
    row = df_results[df_results["Ticker"] == selected].iloc[0]
    df_sel = data_map[selected]

    left, middle, right = st.columns([1.05, 1.3, 2.2])

    with left:
        st.markdown(f"""
        <div class="section-card">
            <div style="font-size:34px;font-weight:800;">{selected}</div>
            <div style="color:#94a3b8 !important;margin-bottom:12px;">{row['Bucket']}</div>
            <div class="badge" style="background:{signal_color(row['Signal'])};">{row['Signal']}</div>
            <div style="margin-top:14px;">Price: <b>{row['Price']}</b></div>
            <div style="margin-top:8px;">1D %: <b>{row['1D %']}</b></div>
            <div style="margin-top:8px;">5D %: <b>{row['5D %']}</b></div>
            <div style="margin-top:8px;">RSI: <b>{row['RSI']}</b></div>
            <div style="margin-top:8px;">MA20: <b>{row['MA20']}</b></div>
            <div style="margin-top:8px;">MA50: <b>{row['MA50']}</b></div>
            <div style="margin-top:8px;">Gap %: <b>{row['Gap %']}</b></div>
            <div style="margin-top:12px;">Reason:</div>
            <div style="margin-top:6px;color:#cbd5e1 !important;">{row['Reason']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")
        b1, b2 = st.columns(2)
        with b1:
            st.link_button("Buy / Trade", fidelity_trade_url(), use_container_width=True)
        with b2:
            st.link_button("Research", fidelity_research_url(), use_container_width=True)

        st.link_button(f"Open {selected} Chart", yahoo_chart_url(selected), use_container_width=True)
        st.link_button(f"Open {selected} Quote", yahoo_quote_url(selected), use_container_width=True)

        msg = action_message(row["Signal"], row["Score"])
        if row["Signal"] == "BUY":
            st.success(msg)
        elif row["Signal"] == "WAIT":
            st.warning(msg)
        elif row["Signal"] == "HOLD":
            st.info(msg)
        else:
            st.error(msg)

        st.caption("Trade buttons open research/trading pages. Orders are still placed manually by you.")

    with middle:
        st.plotly_chart(build_score_gauge(row["Score"], selected), use_container_width=True)

        st.markdown(f"""
        <div class="section-card">
            <div class="metric-label">Trade Notes</div>
            <div style="font-size:16px;line-height:1.7;">
                • Long Term bucket names are meant for slower entries.<br>
                • Aggressive bucket names deserve smaller sizing.<br>
                • WAIT usually means stretched or overheated.<br>
                • BUY means trend is constructive and entry distance is acceptable.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.plotly_chart(build_price_chart(df_sel, selected), use_container_width=True)
        st.plotly_chart(build_rsi_chart(df_sel, selected), use_container_width=True)