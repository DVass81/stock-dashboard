import json
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from ta.momentum import RSIIndicator

st.set_page_config(
    page_title="Trading Terminal Pro",
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

PORTFOLIO_FILE = Path("portfolio_positions.csv")
NOTES_FILE = Path("ticker_notes.json")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #040b16 0%, #0a1220 45%, #0f172a 100%);
}
.block-container {
    padding-top: 1.15rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}
h1, h2, h3, h4, p, div, span, label {
    color: #e5e7eb !important;
}
.hero {
    background: linear-gradient(135deg, #0b1320 0%, #111827 50%, #1e293b 100%);
    border: 1px solid rgba(148, 163, 184, 0.20);
    border-radius: 26px;
    padding: 28px 30px;
    margin-bottom: 18px;
    box-shadow: 0 14px 34px rgba(0,0,0,0.30);
}
.metric-card {
    background: linear-gradient(180deg, #0f172a 0%, #0a1220 100%);
    border: 1px solid rgba(100, 116, 139, 0.25);
    border-radius: 22px;
    padding: 18px;
    min-height: 115px;
    box-shadow: 0 10px 24px rgba(0,0,0,0.22);
}
.metric-label {
    color: #94a3b8 !important;
    font-size: 13px;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.metric-value {
    font-size: 38px;
    font-weight: 800;
    line-height: 1;
}
.section-card {
    background: linear-gradient(180deg, #0f172a 0%, #0a1220 100%);
    border: 1px solid rgba(100, 116, 139, 0.25);
    border-radius: 22px;
    padding: 18px;
    box-shadow: 0 10px 24px rgba(0,0,0,0.22);
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
.big-ticker {
    font-size: 34px;
    font-weight: 800;
    line-height: 1;
}
.kicker {
    color: #93c5fd !important;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
}
div[data-baseweb="select"] * {
    color: black !important;
}
div[data-baseweb="select"] {
    background: white !important;
    border-radius: 10px !important;
}
div[data-testid="stDataEditor"] * {
    color: black !important;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #07101d 0%, #0b1320 100%);
}
</style>
""", unsafe_allow_html=True)

def signal_color(signal):
    return {
        "BUY": "#16a34a",
        "HOLD": "#2563eb",
        "WAIT": "#f59e0b",
        "ERROR": "#dc2626",
        "REDUCE": "#ef4444",
        "REVIEW": "#dc2626",
        "NO POSITION": "#64748b",
    }.get(signal, "#64748b")

def yahoo_chart_url(ticker):
    return f"https://finance.yahoo.com/quote/{quote_plus(ticker)}/chart"

def yahoo_quote_url(ticker):
    return f"https://finance.yahoo.com/quote/{quote_plus(ticker)}"

def fidelity_trade_url():
    return "https://www.fidelity.com/trading/overview"

def fidelity_research_url():
    return "https://digital.fidelity.com/prgw/digital/research/src"

def robinhood_url():
    return "https://robinhood.com/us/en/"

def ensure_portfolio_file():
    if not PORTFOLIO_FILE.exists():
        pd.DataFrame([
            {"Ticker": t, "Shares": 0, "Avg Cost": 0}
            for t in TICKERS
        ]).to_csv(PORTFOLIO_FILE, index=False)

def load_portfolio():
    ensure_portfolio_file()
    df = pd.read_csv(PORTFOLIO_FILE)
    df["Ticker"] = df["Ticker"].astype(str)
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0.0)
    df["Avg Cost"] = pd.to_numeric(df["Avg Cost"], errors="coerce").fillna(0.0)
    return df

def save_portfolio(df):
    df.to_csv(PORTFOLIO_FILE, index=False)

def load_notes():
    if NOTES_FILE.exists():
        try:
            return json.loads(NOTES_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_notes(notes):
    NOTES_FILE.write_text(json.dumps(notes, indent=2))

def get_data(ticker):
    df = yf.download(
        ticker,
        period="6mo",
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    if df.empty or "Close" not in df.columns:
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
    clean["change_1d"] = close.pct_change() * 100
    clean["change_5d"] = close.pct_change(5) * 100
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
    fig.add_trace(go.Scatter(x=df.index, y=df["close"], mode="lines", name="Close", line=dict(width=3)))
    fig.add_trace(go.Scatter(x=df.index, y=df["ma20"], mode="lines", name="MA20", line=dict(width=2)))
    fig.add_trace(go.Scatter(x=df.index, y=df["ma50"], mode="lines", name="MA50", line=dict(width=2, dash="dot")))
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
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], mode="lines", name="RSI", line=dict(width=3)))
    fig.add_hline(y=70, line_dash="dash")
    fig.add_hline(y=30, line_dash="dash")
    fig.update_layout(
        title=f"{ticker} RSI",
        template="plotly_white",
        height=270,
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
            ],
        },
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=10))
    return fig

def position_plan(price, bucket, account_size):
    if bucket == "Aggressive":
        allocation_pct = 0.15
        stop_pct = 0.10
        target_pct = 0.20
    else:
        allocation_pct = 0.25
        stop_pct = 0.08
        target_pct = 0.15

    suggested_dollars = round(account_size * allocation_pct, 2)
    suggested_shares = int(suggested_dollars // price) if price and price > 0 else 0
    stop_price = round(price * (1 - stop_pct), 2)
    target_price = round(price * (1 + target_pct), 2)

    return suggested_dollars, suggested_shares, stop_price, target_price

def holding_action(signal, price, avg_cost, stop_price, target_price, rsi):
    if avg_cost <= 0:
        return "NO POSITION", "No tracked position yet."

    pnl_pct = ((price / avg_cost) - 1) * 100

    if price <= stop_price:
        return "REDUCE", f"Below stop area. P/L {pnl_pct:.1f}%"
    if price >= target_price or rsi >= 75:
        return "REDUCE", f"At target / overheated. P/L {pnl_pct:.1f}%"
    if signal == "WAIT" and pnl_pct > 0:
        return "REVIEW", f"Stretched while in profit. P/L {pnl_pct:.1f}%"
    return "HOLD", f"Within plan. P/L {pnl_pct:.1f}%"

# SIDEBAR
st.sidebar.header("Controls")
account_size = st.sidebar.number_input("Account Size ($)", 100.0, 100000.0, 500.0, 50.0)
refresh_seconds = st.sidebar.slider("Auto refresh (seconds)", 60, 900, 300, 30)
filter_signals = st.sidebar.multiselect(
    "Filter signals",
    ["BUY", "HOLD", "WAIT", "ERROR"],
    default=["BUY", "HOLD", "WAIT", "ERROR"]
)

st.markdown(f"""
<script>
setTimeout(function() {{
    window.location.reload();
}}, {refresh_seconds * 1000});
</script>
""", unsafe_allow_html=True)

# HEADER
st.markdown("""
<div class="hero">
    <div class="kicker">Final Version</div>
    <h1 style="margin:4px 0 8px 0;font-size:52px;">Trading Terminal Pro</h1>
    <p style="margin:0;font-size:18px;color:#cbd5e1 !important;">
        Signals, charts, setup scoring, trade planning, portfolio tracking, notes, and quick broker buttons.
    </p>
</div>
""", unsafe_allow_html=True)

portfolio = load_portfolio()
portfolio_lookup = {
    row["Ticker"]: {"Shares": float(row["Shares"]), "Avg Cost": float(row["Avg Cost"])}
    for _, row in portfolio.iterrows()
}
notes = load_notes()

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
            "Reason": "Not enough valid data",
            "Suggested $": None,
            "Suggested Shares": None,
            "Stop": None,
            "Target": None,
            "Shares Owned": 0,
            "Avg Cost": 0,
            "Market Value": 0,
            "Unrealized P/L": 0,
            "Portfolio Action": "REVIEW",
            "Action Note": "Needs review",
        })
        continue

    data_map[ticker] = df
    signal, score, reason, gap = score_signal(df)

    valid = df.dropna(subset=["close", "rsi", "ma20", "ma50"])
    latest = valid.iloc[-1]

    price = round(float(latest["close"]), 2)
    rsi = round(float(latest["rsi"]), 1)
    ma20 = round(float(latest["ma20"]), 2)
    ma50 = round(float(latest["ma50"]), 2)
    change_1d = round(float(latest["change_1d"]), 2)
    change_5d = round(float(latest["change_5d"]), 2)
    gap = round(float(gap), 2)

    bucket = BUCKETS.get(ticker, "Other")
    suggested_dollars, suggested_shares, stop_price, target_price = position_plan(price, bucket, account_size)

    pos = portfolio_lookup.get(ticker, {"Shares": 0, "Avg Cost": 0})
    shares_owned = float(pos["Shares"])
    avg_cost = float(pos["Avg Cost"])
    market_value = round(shares_owned * price, 2)
    unrealized = round((price - avg_cost) * shares_owned, 2) if shares_owned > 0 else 0
    portfolio_action, action_note = holding_action(signal, price, avg_cost, stop_price, target_price, rsi)

    results.append({
        "Ticker": ticker,
        "Bucket": bucket,
        "Price": price,
        "1D %": change_1d,
        "5D %": change_5d,
        "RSI": rsi,
        "MA20": ma20,
        "MA50": ma50,
        "Gap %": gap,
        "Signal": signal,
        "Score": score,
        "Reason": reason,
        "Suggested $": suggested_dollars,
        "Suggested Shares": suggested_shares,
        "Stop": stop_price,
        "Target": target_price,
        "Shares Owned": shares_owned,
        "Avg Cost": round(avg_cost, 2),
        "Market Value": market_value,
        "Unrealized P/L": unrealized,
        "Portfolio Action": portfolio_action,
        "Action Note": action_note,
    })

df_results = pd.DataFrame(results)
df_results = df_results[df_results["Signal"].isin(filter_signals)]
df_results = df_results.sort_values(by="Score", ascending=False).reset_index(drop=True)

watchlist_size = len(df_results)
buy_count = len(df_results[df_results["Signal"] == "BUY"])
hold_count = len(df_results[df_results["Signal"] == "HOLD"])
wait_count = len(df_results[df_results["Signal"] == "WAIT"])
top_score = int(df_results["Score"].max()) if not df_results.empty else 0
portfolio_value = round(df_results["Market Value"].fillna(0).sum(), 2)

m1, m2, m3, m4, m5, m6 = st.columns(6)

metrics = [
    ("Watchlist", watchlist_size),
    ("BUY", buy_count),
    ("HOLD", hold_count),
    ("WAIT", wait_count),
    ("Top Score", top_score),
    ("Portfolio $", f"{portfolio_value:,.0f}")
]
for col, (label, value) in zip([m1, m2, m3, m4, m5, m6], metrics):
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("### Best Setups Right Now")
top3 = df_results.head(3)
c1, c2, c3 = st.columns(3)

for col, (_, row) in zip([c1, c2, c3], top3.iterrows()):
    with col:
        st.markdown(f"""
        <div class="section-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div class="big-ticker">{row['Ticker']}</div>
                    <div class="small-note">{row['Bucket']}</div>
                </div>
                <div class="badge" style="background:{signal_color(row['Signal'])};">{row['Signal']}</div>
            </div>
            <div style="margin-top:12px;">Score: <b>{row['Score']}</b></div>
            <div style="margin-top:8px;">Price: <b>{row['Price']}</b></div>
            <div style="margin-top:8px;" class="small-note">{row['Reason']}</div>
            <div style="margin-top:10px;">Suggested Buy: <b>${row['Suggested $']}</b></div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("### Quick Read")
q1, q2, q3, q4 = st.columns(4)

if not df_results.empty:
    strongest = df_results.iloc[0]["Ticker"]
    hottest = df_results.sort_values("1D %", ascending=False).iloc[0]["Ticker"]
    coolest = df_results.sort_values("RSI", ascending=True).iloc[0]["Ticker"]
    biggest_gap = df_results.sort_values("Gap %", ascending=False).iloc[0]["Ticker"]
else:
    strongest = hottest = coolest = biggest_gap = "N/A"

for col, label, value in [
    (q1, "Strongest Setup", strongest),
    (q2, "Best 1-Day Move", hottest),
    (q3, "Most Cooled Off", coolest),
    (q4, "Most Extended", biggest_gap),
]:
    with col:
        st.markdown(f"""
        <div class="section-card">
            <div class="metric-label">{label}</div>
            <div style="font-size:28px;font-weight:800;">{value}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("### Ranked Watchlist")
st.dataframe(
    df_results[[
        "Ticker", "Bucket", "Price", "1D %", "5D %", "RSI", "MA20", "MA50", "Gap %",
        "Signal", "Score", "Suggested $", "Suggested Shares", "Stop", "Target",
        "Shares Owned", "Avg Cost", "Market Value", "Unrealized P/L", "Portfolio Action"
    ]],
    use_container_width=True,
    hide_index=True
)

st.markdown("### Portfolio Tracker")
st.caption("Edit your shares and average cost, then save.")
edited_portfolio = st.data_editor(
    portfolio,
    use_container_width=True,
    num_rows="fixed",
    hide_index=True,
    key="portfolio_editor"
)
if st.button("Save Portfolio"):
    edited_portfolio["Shares"] = pd.to_numeric(edited_portfolio["Shares"], errors="coerce").fillna(0)
    edited_portfolio["Avg Cost"] = pd.to_numeric(edited_portfolio["Avg Cost"], errors="coerce").fillna(0)
    save_portfolio(edited_portfolio)
    st.success("Portfolio saved. Refresh the page to update calculations.")

st.markdown("### Terminal Detail")
selected = st.selectbox("Choose a ticker", df_results["Ticker"].tolist())

if selected in data_map:
    row = df_results[df_results["Ticker"] == selected].iloc[0]
    df_sel = data_map[selected]

    left, mid, right = st.columns([1.05, 1.15, 2.1])

    with left:
        st.markdown(f"""
        <div class="section-card">
            <div class="big-ticker">{selected}</div>
            <div class="small-note" style="margin-bottom:12px;">{row['Bucket']}</div>
            <div class="badge" style="background:{signal_color(row['Signal'])};">{row['Signal']}</div>
            <div style="margin-top:14px;">Price: <b>{row['Price']}</b></div>
            <div style="margin-top:8px;">1D %: <b>{row['1D %']}</b></div>
            <div style="margin-top:8px;">5D %: <b>{row['5D %']}</b></div>
            <div style="margin-top:8px;">RSI: <b>{row['RSI']}</b></div>
            <div style="margin-top:8px;">MA20: <b>{row['MA20']}</b></div>
            <div style="margin-top:8px;">MA50: <b>{row['MA50']}</b></div>
            <div style="margin-top:8px;">Gap %: <b>{row['Gap %']}</b></div>
            <div style="margin-top:12px;">Reason:</div>
            <div class="small-note" style="margin-top:6px;">{row['Reason']}</div>
        </div>
        """, unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        with b1:
            st.link_button("Fidelity", fidelity_trade_url(), use_container_width=True)
        with b2:
            st.link_button("Robinhood", robinhood_url(), use_container_width=True)

        cta1, cta2 = st.columns(2)
        with cta1:
            st.link_button("Research", fidelity_research_url(), use_container_width=True)
        with cta2:
            st.link_button("Yahoo Chart", yahoo_chart_url(selected), use_container_width=True)

        st.link_button("Yahoo Quote", yahoo_quote_url(selected), use_container_width=True)

    with mid:
        st.plotly_chart(build_score_gauge(row["Score"], selected), use_container_width=True)

        st.markdown(f"""
        <div class="section-card">
            <div class="metric-label">Trade Plan</div>
            <div style="margin-top:10px;">Suggested Buy: <b>${row['Suggested $']}</b></div>
            <div style="margin-top:8px;">Suggested Shares: <b>{row['Suggested Shares']}</b></div>
            <div style="margin-top:8px;">Stop Loss: <b>{row['Stop']}</b></div>
            <div style="margin-top:8px;">Target Price: <b>{row['Target']}</b></div>
            <div style="margin-top:8px;">Portfolio Action:
                <span class="badge" style="background:{signal_color(row['Portfolio Action'])};">{row['Portfolio Action']}</span>
            </div>
            <div class="small-note" style="margin-top:8px;">{row['Action Note']}</div>
        </div>
        """, unsafe_allow_html=True)

        current_note = notes.get(selected, "")
        new_note = st.text_area("Ticker Notes", value=current_note, height=160, key=f"note_{selected}")
        if st.button("Save Note", key=f"save_{selected}"):
            notes[selected] = new_note
            save_notes(notes)
            st.success(f"Saved note for {selected}")

    with right:
        st.plotly_chart(build_price_chart(df_sel, selected), use_container_width=True)
        st.plotly_chart(build_rsi_chart(df_sel, selected), use_container_width=True)