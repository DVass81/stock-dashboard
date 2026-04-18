import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from openai import OpenAI
from ta.momentum import RSIIndicator

st.set_page_config(
    page_title="Trading Terminal Supreme",
    page_icon="📈",
    layout="wide"
)

# ============================================================
# CONFIG
# ============================================================
TICKERS = [
    "NVDA", "MSFT", "AMZN", "GOOGL", "SOUN", "RGTI", "PLUG", "BFGFF",
    "BTC-USD", "ETH-USD", "ADA-USD", "SHIB-USD"
]

BUCKETS = {
    "NVDA": "Long Term",
    "MSFT": "Long Term",
    "AMZN": "Long Term",
    "GOOGL": "Long Term",
    "SOUN": "Aggressive",
    "RGTI": "Aggressive",
    "PLUG": "Aggressive",
    "BFGFF": "Speculative",
    "BTC-USD": "Crypto",
    "ETH-USD": "Crypto",
    "ADA-USD": "Crypto",
    "SHIB-USD": "Crypto",
}

ACTIONS = ["BUY", "SELL"]
REASONS = [
    "Trend Trade",
    "Pullback Buy",
    "Breakout",
    "Speculative",
    "Crypto Swing",
    "Rebalance",
    "Other",
]

JOURNAL_FILE = Path("trade_journal.csv")
NOTES_FILE = Path("ticker_notes.json")
ALERT_STATE_FILE = Path("alert_state.json")
ALERT_HISTORY_FILE = Path("alert_history.json")

# ============================================================
# STYLING
# ============================================================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 40%, #334155 100%);
}
.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    max-width: 1650px;
}
.hero {
    background: linear-gradient(135deg, #22c55e 0%, #2563eb 38%, #9333ea 100%);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 28px;
    padding: 28px 32px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.28);
    margin-bottom: 16px;
}
.metric-card {
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    border: 1px solid rgba(148, 163, 184, 0.30);
    border-radius: 22px;
    padding: 18px;
    min-height: 110px;
    box-shadow: 0 10px 26px rgba(0,0,0,0.14);
}
.metric-label {
    color: #334155 !important;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
    font-weight: 700;
}
.metric-value {
    color: #0f172a !important;
    font-size: 38px;
    font-weight: 800;
    line-height: 1;
}
.card {
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 22px;
    padding: 18px;
    box-shadow: 0 10px 26px rgba(0,0,0,0.12);
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
.h-chip {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 12px;
    color: white !important;
}
.dark { color: #0f172a !important; }
.muted { color: #475569 !important; }
.big-ticker {
    color: #0f172a !important;
    font-size: 34px;
    font-weight: 800;
    line-height: 1;
}
.kicker {
    color: #dbeafe !important;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
}
.good { color: #15803d !important; font-weight: 800; }
.warn { color: #d97706 !important; font-weight: 800; }
.bad { color: #dc2626 !important; font-weight: 800; }
div[data-baseweb="select"] * { color: black !important; }
div[data-baseweb="select"] { background: white !important; border-radius: 10px !important; }
div[data-testid="stDataEditor"] * { color: black !important; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
}
[data-testid="stDataFrame"] * { color: black !important; }
.stTabs [data-baseweb="tab"] * { color: black !important; }
.stTabs [role="tab"][aria-selected="true"] {
    background: white !important;
    border-radius: 12px 12px 0 0 !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# FILE HELPERS
# ============================================================
def load_json_file(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return default
    return default


def save_json_file(path: Path, value):
    path.write_text(json.dumps(value, indent=2))


def ensure_journal_file():
    if not JOURNAL_FILE.exists():
        pd.DataFrame(columns=[
            "Date", "Ticker", "Action", "Reason", "Price", "Shares", "Fees", "Notes"
        ]).to_csv(JOURNAL_FILE, index=False)


def load_journal():
    ensure_journal_file()
    df = pd.read_csv(JOURNAL_FILE)
    if df.empty:
        return pd.DataFrame(columns=["Date", "Ticker", "Action", "Reason", "Price", "Shares", "Fees", "Notes"])
    for col in ["Price", "Shares", "Fees"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Ticker"] = df["Ticker"].astype(str)
    df["Action"] = df["Action"].astype(str).str.upper()
    if "Reason" not in df.columns:
        df["Reason"] = "Other"
    df["Reason"] = df["Reason"].astype(str)
    df["Notes"] = df["Notes"].astype(str)
    return df.sort_values("Date", kind="stable").reset_index(drop=True)


def save_journal(df):
    out = df.copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out.to_csv(JOURNAL_FILE, index=False)


def load_notes():
    return load_json_file(NOTES_FILE, {})


def save_notes(notes):
    save_json_file(NOTES_FILE, notes)


def load_alert_state():
    return load_json_file(ALERT_STATE_FILE, {})


def save_alert_state(state):
    save_json_file(ALERT_STATE_FILE, state)


def load_alert_history():
    return load_json_file(ALERT_HISTORY_FILE, [])


def save_alert_history(history):
    save_json_file(ALERT_HISTORY_FILE, history[:250])

# ============================================================
# GENERAL HELPERS
# ============================================================
def signal_color(signal):
    return {
        "STRONG BUY": "#15803d",
        "BUY": "#22c55e",
        "HOLD": "#3b82f6",
        "WAIT": "#f59e0b",
        "ERROR": "#ef4444",
        "REDUCE": "#ef4444",
        "REVIEW": "#f97316",
        "NO POSITION": "#64748b",
    }.get(signal, "#64748b")


def bucket_color(bucket):
    return {
        "Long Term": "#2563eb",
        "Aggressive": "#f97316",
        "Speculative": "#9333ea",
        "Crypto": "#14b8a6",
    }.get(bucket, "#64748b")


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


def coinbase_url():
    return "https://www.coinbase.com/"


def arrow_text(value):
    if pd.isna(value):
        return "—"
    if value > 0:
        return f"▲ {value:.2f}%"
    if value < 0:
        return f"▼ {value:.2f}%"
    return f"{value:.2f}%"


def market_banner():
    st.success("📡 Live dashboard. Stocks follow market hours. Crypto updates continuously.")


def get_openai_client():
    api_key = st.secrets.get("OPENAI_API_KEY", None)
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

# ============================================================
# DATA + SIGNALS
# ============================================================
@st.cache_data(ttl=300)
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
    clean["change_1d"] = close.pct_change() * 100
    clean["change_5d"] = close.pct_change(5) * 100
    clean["distance_ma20"] = ((clean["close"] / clean["ma20"]) - 1) * 100
    clean["vol20"] = clean["close"].pct_change().rolling(20).std() * 100

    valid = clean.dropna(subset=["close", "rsi", "ma20", "ma50"])
    return None if valid.empty else clean


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

    if close > ma20 and ma20 > ma50 and rsi < 62 and gap <= 3:
        signal = "STRONG BUY"
    elif close > ma20 and ma20 > ma50 and rsi < 70 and gap <= 5:
        signal = "BUY"
    elif rsi > 75 or gap > 8:
        signal = "WAIT"
    else:
        signal = "HOLD"

    return signal, int(score), "; ".join(reasons), gap


def position_plan(price, bucket, account_size):
    if bucket == "Aggressive":
        allocation_pct = 0.15
        stop_pct = 0.10
        target_pct = 0.20
    elif bucket == "Crypto":
        allocation_pct = 0.10
        stop_pct = 0.12
        target_pct = 0.22
    elif bucket == "Speculative":
        allocation_pct = 0.10
        stop_pct = 0.12
        target_pct = 0.20
    else:
        allocation_pct = 0.25
        stop_pct = 0.08
        target_pct = 0.15

    suggested_dollars = round(account_size * allocation_pct, 2)
    suggested_shares = round(suggested_dollars / price, 6) if price and price > 0 else 0
    if bucket != "Crypto":
        suggested_shares = int(suggested_dollars // price) if price and price > 0 else 0

    stop_price = round(price * (1 - stop_pct), 4)
    target_price = round(price * (1 + target_pct), 4)
    rr = round((target_price - price) / max(price - stop_price, 0.0001), 2) if price > stop_price else None

    return suggested_dollars, suggested_shares, stop_price, target_price, rr


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

# ============================================================
# JOURNAL -> PORTFOLIO / PERFORMANCE
# ============================================================
def build_portfolio_from_journal(journal, price_lookup):
    positions = {}

    if journal.empty:
        return pd.DataFrame(columns=[
            "Ticker", "Bucket", "Shares Owned", "Avg Cost", "Current Price",
            "Cost Basis", "Market Value", "Unrealized P/L"
        ])

    work = journal.dropna(subset=["Date"]).sort_values("Date", kind="stable")
    for _, row in work.iterrows():
        ticker = row["Ticker"]
        action = str(row["Action"]).upper()
        shares = float(row["Shares"])
        price = float(row["Price"])
        fees = float(row["Fees"])

        if ticker not in positions:
            positions[ticker] = {"shares": 0.0, "cost_basis_total": 0.0}

        pos = positions[ticker]

        if action == "BUY":
            pos["shares"] += shares
            pos["cost_basis_total"] += (shares * price) + fees
        elif action == "SELL":
            if pos["shares"] <= 0:
                continue
            avg_cost = pos["cost_basis_total"] / pos["shares"] if pos["shares"] else 0
            sell_shares = min(shares, pos["shares"])
            pos["shares"] -= sell_shares
            pos["cost_basis_total"] -= avg_cost * sell_shares
            pos["cost_basis_total"] = max(pos["cost_basis_total"], 0)

    rows = []
    for ticker, pos in positions.items():
        shares_owned = round(pos["shares"], 6)
        if shares_owned <= 0:
            continue
        current_price = price_lookup.get(ticker, 0)
        cost_basis = round(pos["cost_basis_total"], 2)
        avg_cost = round(cost_basis / shares_owned, 4) if shares_owned else 0
        market_value = round(current_price * shares_owned, 2)
        unrealized = round(market_value - cost_basis, 2)

        rows.append({
            "Ticker": ticker,
            "Bucket": BUCKETS.get(ticker, "Other"),
            "Shares Owned": shares_owned,
            "Avg Cost": avg_cost,
            "Current Price": round(current_price, 4) if "USD" in ticker and ticker not in ["BTC-USD", "ETH-USD"] else round(current_price, 2),
            "Cost Basis": cost_basis,
            "Market Value": market_value,
            "Unrealized P/L": unrealized,
        })

    return pd.DataFrame(rows).sort_values("Market Value", ascending=False).reset_index(drop=True) if rows else pd.DataFrame(columns=[
        "Ticker", "Bucket", "Shares Owned", "Avg Cost", "Current Price",
        "Cost Basis", "Market Value", "Unrealized P/L"
    ])


def build_performance_series(journal, price_lookup):
    if journal.empty:
        return pd.DataFrame(columns=["Date", "Invested Capital", "Current Value"])

    dates = sorted(pd.to_datetime(journal["Date"], errors="coerce").dropna().dt.date.unique())
    if not dates:
        return pd.DataFrame(columns=["Date", "Invested Capital", "Current Value"])

    rows = []
    for d in dates:
        subset = journal[pd.to_datetime(journal["Date"], errors="coerce").dt.date <= d].copy()
        temp_port = build_portfolio_from_journal(subset, price_lookup)
        invested = float(temp_port["Cost Basis"].sum()) if not temp_port.empty else 0.0
        current = float(temp_port["Market Value"].sum()) if not temp_port.empty else 0.0
        rows.append({
            "Date": pd.to_datetime(d),
            "Invested Capital": round(invested, 2),
            "Current Value": round(current, 2)
        })
    return pd.DataFrame(rows)


def build_portfolio_health(portfolio_df):
    if portfolio_df.empty:
        return {
            "score": "No Positions",
            "concentration": 0,
            "crypto_pct": 0,
            "spec_pct": 0,
            "top_ticker": "N/A",
            "risk_note": "Add trades in Journal to build a portfolio."
        }

    total_value = portfolio_df["Market Value"].sum()
    by_ticker = portfolio_df.sort_values("Market Value", ascending=False)
    top_ticker = by_ticker.iloc[0]["Ticker"]
    concentration = round((by_ticker.iloc[0]["Market Value"] / total_value) * 100, 1) if total_value > 0 else 0

    crypto_value = portfolio_df[portfolio_df["Bucket"] == "Crypto"]["Market Value"].sum()
    spec_value = portfolio_df[portfolio_df["Bucket"].isin(["Speculative", "Aggressive"])]["Market Value"].sum()
    crypto_pct = round((crypto_value / total_value) * 100, 1) if total_value > 0 else 0
    spec_pct = round((spec_value / total_value) * 100, 1) if total_value > 0 else 0

    if concentration > 40 or crypto_pct > 40 or spec_pct > 55:
        score = "Overextended"
        note = "High concentration or aggressive exposure."
    elif concentration > 28 or crypto_pct > 25 or spec_pct > 40:
        score = "Aggressive"
        note = "Portfolio is leaning risk-on."
    elif concentration > 20:
        score = "Balanced"
        note = "Reasonable but watch concentration."
    else:
        score = "Stable"
        note = "Diversification looks healthy."

    return {
        "score": score,
        "concentration": concentration,
        "crypto_pct": crypto_pct,
        "spec_pct": spec_pct,
        "top_ticker": top_ticker,
        "risk_note": note
    }

# ============================================================
# ALERTS / NEWS / CHAT
# ============================================================
def maybe_record_alerts(results_df):
    state = load_alert_state()
    history = load_alert_history()

    for _, row in results_df.iterrows():
        ticker = row["Ticker"]
        new_signal = row["Signal"]
        old_signal = state.get(ticker)

        if old_signal is not None and old_signal != new_signal:
            history.insert(0, {
                "Timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "Ticker": ticker,
                "From": old_signal,
                "To": new_signal,
                "Price": row["Price"],
                "Score": row["Score"]
            })

        state[ticker] = new_signal

    save_alert_state(state)
    save_alert_history(history)

@st.cache_data(ttl=900)
def get_news(ticker):
    symbol = ticker.replace("-USD", "")
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:6]:
            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", "")
            })
        return items
    except Exception:
        return []

# ============================================================
# CHARTS
# ============================================================
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


def build_portfolio_bar(df):
    if df.empty:
        return None
    fig = go.Figure(go.Bar(x=df["Ticker"], y=df["Market Value"]))
    fig.update_layout(
        title="Portfolio Value by Ticker",
        template="plotly_white",
        height=320,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig


def build_performance_chart(perf_df):
    if perf_df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=perf_df["Date"], y=perf_df["Invested Capital"], mode="lines", name="Invested Capital"))
    fig.add_trace(go.Scatter(x=perf_df["Date"], y=perf_df["Current Value"], mode="lines", name="Current Value"))
    fig.update_layout(
        title="Invested Capital vs Current Value",
        template="plotly_white",
        height=320,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h")
    )
    return fig

# ============================================================
# SIDEBAR / HEADER
# ============================================================
st.sidebar.header("Controls")
account_size = st.sidebar.number_input("Account Size ($)", 100.0, 100000.0, 500.0, 50.0)
refresh_seconds = st.sidebar.slider("Auto refresh (seconds)", 60, 900, 300, 30)
filter_signals = st.sidebar.multiselect(
    "Filter signals",
    ["STRONG BUY", "BUY", "HOLD", "WAIT", "ERROR"],
    default=["STRONG BUY", "BUY", "HOLD", "WAIT", "ERROR"]
)

st.markdown(f"""
<script>
setTimeout(function() {{
    window.location.reload();
}}, {refresh_seconds * 1000});
</script>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <div class="kicker">Final All-In Build</div>
    <h1 style="margin:4px 0 8px 0;font-size:52px;">Trading Terminal Supreme</h1>
    <p style="margin:0;font-size:18px;color:#ffffff !important;">
        Command center, scanner, journal-driven portfolio, health score, signals, news, alerts, broker buttons, and AI assistant.
    </p>
</div>
""", unsafe_allow_html=True)

market_banner()

# ============================================================
# BUILD DATA
# ============================================================
notes = load_notes()
journal = load_journal()

results = []
data_map = {}
price_lookup = {}

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
            "R/R": None,
        })
        continue

    data_map[ticker] = df
    signal, score, reason, gap = score_signal(df)
    valid = df.dropna(subset=["close", "rsi", "ma20", "ma50"])
    latest = valid.iloc[-1]
    price = float(latest["close"])
    price_lookup[ticker] = price

    bucket = BUCKETS.get(ticker, "Other")
    suggested_dollars, suggested_shares, stop_price, target_price, rr = position_plan(price, bucket, account_size)

    results.append({
        "Ticker": ticker,
        "Bucket": bucket,
        "Price": round(price, 4) if "USD" in ticker and ticker not in ["BTC-USD", "ETH-USD"] else round(price, 2),
        "1D %": round(float(latest["change_1d"]), 2),
        "5D %": round(float(latest["change_5d"]), 2),
        "RSI": round(float(latest["rsi"]), 1),
        "MA20": round(float(latest["ma20"]), 4) if "USD" in ticker and ticker not in ["BTC-USD", "ETH-USD"] else round(float(latest["ma20"]), 2),
        "MA50": round(float(latest["ma50"]), 4) if "USD" in ticker and ticker not in ["BTC-USD", "ETH-USD"] else round(float(latest["ma50"]), 2),
        "Gap %": round(float(gap), 2),
        "Signal": signal,
        "Score": score,
        "Reason": reason,
        "Suggested $": suggested_dollars,
        "Suggested Shares": suggested_shares,
        "Stop": stop_price,
        "Target": target_price,
        "R/R": rr,
    })

market_df = pd.DataFrame(results)
market_df = market_df[market_df["Signal"].isin(filter_signals)].sort_values(by="Score", ascending=False).reset_index(drop=True)

portfolio_df = build_portfolio_from_journal(journal, price_lookup)
perf_df = build_performance_series(journal, price_lookup)
health = build_portfolio_health(portfolio_df)

portfolio_lookup = {}
if not portfolio_df.empty:
    for _, row in portfolio_df.iterrows():
        portfolio_lookup[row["Ticker"]] = row

enriched = []
for _, row in market_df.iterrows():
    t = row["Ticker"]
    port = portfolio_lookup.get(t)
    shares_owned = float(port["Shares Owned"]) if port is not None else 0.0
    avg_cost = float(port["Avg Cost"]) if port is not None else 0.0
    market_value = float(port["Market Value"]) if port is not None else 0.0
    unrealized = float(port["Unrealized P/L"]) if port is not None else 0.0
    action, action_note = holding_action(
        row["Signal"],
        float(row["Price"]) if pd.notna(row["Price"]) else 0,
        avg_cost,
        float(row["Stop"]) if pd.notna(row["Stop"]) else 0,
        float(row["Target"]) if pd.notna(row["Target"]) else 0,
        float(row["RSI"]) if pd.notna(row["RSI"]) else 0
    )
    item = row.to_dict()
    item["Shares Owned"] = shares_owned
    item["Avg Cost"] = round(avg_cost, 4)
    item["Market Value"] = round(market_value, 2)
    item["Unrealized P/L"] = round(unrealized, 2)
    item["Portfolio Action"] = action
    item["Action Note"] = action_note
    enriched.append(item)

df_results = pd.DataFrame(enriched)
maybe_record_alerts(df_results)

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["Command Center", "Dashboard", "Scanner", "Portfolio", "Journal", "News & Alerts", "Chatbot"]
)

with tab1:
    st.subheader("Command Center")
    top_signal_changes = load_alert_history()[:5]

    c1, c2 = st.columns([1.4, 1.0])

    with c1:
        if not df_results.empty:
            top = df_results.iloc[0]
            st.markdown(f"""
            <div class="card">
                <div class="metric-label">Top Opportunity Right Now</div>
                <div class="big-ticker">{top['Ticker']}</div>
                <div style="margin-top:8px;"><span class="badge" style="background:{signal_color(top['Signal'])};">{top['Signal']}</span></div>
                <div class="dark" style="margin-top:12px;">Score: <b>{top['Score']}</b></div>
                <div class="dark" style="margin-top:8px;">Suggested Buy: <b>${top['Suggested $']}</b></div>
                <div class="muted" style="margin-top:8px;">{top['Reason']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### Morning Briefing")
        brief = []
        if not df_results.empty:
            strong_count = len(df_results[df_results["Signal"] == "STRONG BUY"])
            buy_count = len(df_results[df_results["Signal"] == "BUY"])
            hottest = df_results.sort_values("1D %", ascending=False).iloc[0]["Ticker"]
            weakest = df_results.sort_values("1D %").iloc[0]["Ticker"]
            brief = [
                f"Strong Buy setups: {strong_count}",
                f"Buy setups: {buy_count}",
                f"Best 1-day mover: {hottest}",
                f"Weakest 1-day mover: {weakest}",
                f"Portfolio health: {health['score']}",
            ]
        for item in brief:
            st.markdown(f"- {item}")

    with c2:
        st.markdown(f"""
        <div class="card">
            <div class="metric-label">Portfolio Health</div>
            <div class="big-ticker">{health['score']}</div>
            <div class="dark" style="margin-top:10px;">Top concentration: <b>{health['concentration']}%</b></div>
            <div class="dark" style="margin-top:8px;">Crypto exposure: <b>{health['crypto_pct']}%</b></div>
            <div class="dark" style="margin-top:8px;">Aggressive/Spec exposure: <b>{health['spec_pct']}%</b></div>
            <div class="dark" style="margin-top:8px;">Largest position: <b>{health['top_ticker']}</b></div>
            <div class="muted" style="margin-top:10px;">{health['risk_note']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### What Changed")
        if not top_signal_changes:
            st.info("No signal changes recorded yet.")
        else:
            for alert in top_signal_changes:
                st.markdown(f"""
                <div class="card" style="margin-bottom:10px;">
                    <div class="dark" style="font-weight:700;">{alert['Ticker']}: {alert['From']} → {alert['To']}</div>
                    <div class="muted" style="margin-top:6px;">{alert['Timestamp']} | Price {alert['Price']} | Score {alert['Score']}</div>
                </div>
                """, unsafe_allow_html=True)

with tab2:
    watchlist_size = len(df_results)
    strong_buy_count = len(df_results[df_results["Signal"] == "STRONG BUY"])
    buy_count = len(df_results[df_results["Signal"] == "BUY"])
    hold_count = len(df_results[df_results["Signal"] == "HOLD"])
    portfolio_value = round(df_results["Market Value"].fillna(0).sum(), 2)
    unrealized_total = round(df_results["Unrealized P/L"].fillna(0).sum(), 2)

    cols = st.columns(6)
    metrics = [
        ("Watchlist", watchlist_size),
        ("Strong Buy", strong_buy_count),
        ("Buy", buy_count),
        ("Hold", hold_count),
        ("Portfolio $", f"{portfolio_value:,.0f}"),
        ("Unrealized P/L", f"{unrealized_total:,.0f}")
    ]
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("### Top Opportunities")
    top3 = df_results.head(3)
    card_cols = st.columns(3)
    for col, (_, row) in zip(card_cols, top3.iterrows()):
        with col:
            st.markdown(f"""
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div class="big-ticker">{row['Ticker']}</div>
                        <div class="muted">{row['Bucket']}</div>
                    </div>
                    <div class="badge" style="background:{signal_color(row['Signal'])};">{row['Signal']}</div>
                </div>
                <div class="dark" style="margin-top:12px;">Score: <b>{row['Score']}</b></div>
                <div class="dark" style="margin-top:8px;">Price: <b>{row['Price']}</b></div>
                <div class="muted" style="margin-top:8px;">{row['Reason']}</div>
                <div class="dark" style="margin-top:10px;">Suggested Buy: <b>${row['Suggested $']}</b></div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("### Watchlist")
    display_df = df_results.copy()
    display_df["1D Move"] = display_df["1D %"].apply(arrow_text)
    display_df["5D Move"] = display_df["5D %"].apply(arrow_text)
    st.dataframe(
        display_df[[
            "Ticker", "Bucket", "Price", "1D Move", "5D Move", "RSI", "MA20", "MA50",
            "Gap %", "Signal", "Score", "Suggested $", "Suggested Shares", "Stop", "Target", "R/R",
            "Shares Owned", "Avg Cost", "Market Value", "Unrealized P/L", "Portfolio Action"
        ]],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("### Terminal Detail")
    selected = st.selectbox("Choose a ticker", df_results["Ticker"].tolist(), key="detail_ticker")
    if selected in data_map:
        row = df_results[df_results["Ticker"] == selected].iloc[0]
        df_sel = data_map[selected]
        left, mid, right = st.columns([1.05, 1.15, 2.1])

        with left:
            st.markdown(f"""
            <div class="card">
                <div class="big-ticker">{selected}</div>
                <div class="muted" style="margin-bottom:10px;">{row['Bucket']}</div>
                <div class="h-chip" style="background:{bucket_color(row['Bucket'])};">{row['Bucket']}</div>
                <div class="badge" style="background:{signal_color(row['Signal'])}; margin-top:10px;">{row['Signal']}</div>
                <div class="dark" style="margin-top:14px;">Price: <b>{row['Price']}</b></div>
                <div class="dark" style="margin-top:8px;">1D %: <b>{row['1D %']}</b></div>
                <div class="dark" style="margin-top:8px;">5D %: <b>{row['5D %']}</b></div>
                <div class="dark" style="margin-top:8px;">RSI: <b>{row['RSI']}</b></div>
                <div class="dark" style="margin-top:8px;">MA20: <b>{row['MA20']}</b></div>
                <div class="dark" style="margin-top:8px;">MA50: <b>{row['MA50']}</b></div>
                <div class="dark" style="margin-top:8px;">Gap %: <b>{row['Gap %']}</b></div>
                <div class="dark" style="margin-top:12px;">Reason:</div>
                <div class="muted" style="margin-top:6px;">{row['Reason']}</div>
            </div>
            """, unsafe_allow_html=True)

            b1, b2, b3 = st.columns(3)
            with b1:
                st.link_button("Fidelity", fidelity_trade_url(), use_container_width=True)
            with b2:
                st.link_button("Robinhood", robinhood_url(), use_container_width=True)
            with b3:
                st.link_button("Coinbase", coinbase_url(), use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                st.link_button("Research", fidelity_research_url(), use_container_width=True)
            with c2:
                st.link_button("Yahoo Chart", yahoo_chart_url(selected), use_container_width=True)
            st.link_button("Yahoo Quote", yahoo_quote_url(selected), use_container_width=True)

        with mid:
            st.plotly_chart(build_score_gauge(row["Score"], selected), use_container_width=True)
            st.markdown(f"""
            <div class="card">
                <div class="metric-label">Trade Plan</div>
                <div class="dark" style="margin-top:10px;">Suggested Buy: <b>${row['Suggested $']}</b></div>
                <div class="dark" style="margin-top:8px;">Suggested Shares: <b>{row['Suggested Shares']}</b></div>
                <div class="dark" style="margin-top:8px;">Stop Loss: <b>{row['Stop']}</b></div>
                <div class="dark" style="margin-top:8px;">Target Price: <b>{row['Target']}</b></div>
                <div class="dark" style="margin-top:8px;">Risk/Reward: <b>{row['R/R']}</b></div>
                <div class="dark" style="margin-top:8px;">Portfolio Action:
                    <span class="badge" style="background:{signal_color(row['Portfolio Action'])};">{row['Portfolio Action']}</span>
                </div>
                <div class="muted" style="margin-top:8px;">{row['Action Note']}</div>
            </div>
            """, unsafe_allow_html=True)

            current_note = notes.get(selected, "")
            new_note = st.text_area("Ticker Notes", value=current_note, height=160, key=f"note_{selected}")
            if st.button("Save Note", key=f"save_note_{selected}"):
                notes[selected] = new_note
                save_notes(notes)
                st.success(f"Saved note for {selected}")

        with right:
            st.plotly_chart(build_price_chart(df_sel, selected), use_container_width=True)
            st.plotly_chart(build_rsi_chart(df_sel, selected), use_container_width=True)

with tab3:
    st.subheader("Opportunity Scanner")
    c1, c2, c3, c4 = st.columns(4)
    strong_df = df_results[df_results["Signal"] == "STRONG BUY"]
    buy_df = df_results[df_results["Signal"] == "BUY"]
    cooled_df = df_results.sort_values("RSI").head(5)
    extended_df = df_results.sort_values("Gap %", ascending=False).head(5)

    with c1:
        st.markdown("#### Strong Buy")
        st.dataframe(
            strong_df[["Ticker", "Price", "RSI", "Score", "Suggested $"]] if not strong_df.empty else pd.DataFrame(columns=["Ticker", "Price", "RSI", "Score", "Suggested $"]),
            use_container_width=True, hide_index=True
        )
    with c2:
        st.markdown("#### Buy")
        st.dataframe(
            buy_df[["Ticker", "Price", "RSI", "Score", "Suggested $"]] if not buy_df.empty else pd.DataFrame(columns=["Ticker", "Price", "RSI", "Score", "Suggested $"]),
            use_container_width=True, hide_index=True
        )
    with c3:
        st.markdown("#### Most Cooled Off")
        st.dataframe(cooled_df[["Ticker", "RSI", "1D %", "5D %"]], use_container_width=True, hide_index=True)
    with c4:
        st.markdown("#### Most Extended")
        st.dataframe(extended_df[["Ticker", "Gap %", "RSI", "1D %"]], use_container_width=True, hide_index=True)

    st.markdown("### Grouped by Style")
    for bucket in ["Long Term", "Aggressive", "Speculative", "Crypto"]:
        sub = df_results[df_results["Bucket"] == bucket]
        st.markdown(f"#### {bucket}")
        if sub.empty:
            st.info(f"No {bucket} setups right now.")
        else:
            st.dataframe(sub[["Ticker", "Signal", "Score", "Price", "RSI", "1D %", "Suggested $"]], use_container_width=True, hide_index=True)

with tab4:
    st.subheader("Portfolio")
    if portfolio_df.empty:
        st.info("No open positions yet. Add buys and sells in the Journal tab.")
    else:
        st.dataframe(portfolio_df, use_container_width=True, hide_index=True)

        p1, p2 = st.columns(2)
        with p1:
            bar = build_portfolio_bar(portfolio_df)
            if bar is not None:
                st.plotly_chart(bar, use_container_width=True)
        with p2:
            perf = build_performance_chart(perf_df)
            if perf is not None:
                st.plotly_chart(perf, use_container_width=True)

        st.markdown(f"""
        <div class="card">
            <div class="metric-label">Portfolio Health Summary</div>
            <div class="dark" style="font-size:28px;font-weight:800;">{health['score']}</div>
            <div class="dark" style="margin-top:10px;">Top position concentration: <b>{health['concentration']}%</b></div>
            <div class="dark" style="margin-top:8px;">Crypto exposure: <b>{health['crypto_pct']}%</b></div>
            <div class="dark" style="margin-top:8px;">Spec/Aggressive exposure: <b>{health['spec_pct']}%</b></div>
            <div class="muted" style="margin-top:10px;">{health['risk_note']}</div>
        </div>
        """, unsafe_allow_html=True)

with tab5:
    st.subheader("Trade Journal")
    st.caption("This journal drives the portfolio automatically.")

    form_col, table_col = st.columns([1.0, 1.35])

    with form_col:
        st.markdown("### Add Journal Entry")
        j_date = st.date_input("Date", value=datetime.today())
        j_ticker = st.selectbox("Ticker", TICKERS, key="journal_ticker")
        j_action = st.selectbox("Action", ACTIONS, key="journal_action")
        j_reason = st.selectbox("Reason", REASONS, key="journal_reason")

        current_market_price = price_lookup.get(j_ticker, 0.0)
        current_signal = df_results[df_results["Ticker"] == j_ticker]["Signal"].iloc[0] if not df_results[df_results["Ticker"] == j_ticker].empty else "N/A"
        suggested_shares = df_results[df_results["Ticker"] == j_ticker]["Suggested Shares"].iloc[0] if not df_results[df_results["Ticker"] == j_ticker].empty else 0
        stop_val = df_results[df_results["Ticker"] == j_ticker]["Stop"].iloc[0] if not df_results[df_results["Ticker"] == j_ticker].empty else 0
        target_val = df_results[df_results["Ticker"] == j_ticker]["Target"].iloc[0] if not df_results[df_results["Ticker"] == j_ticker].empty else 0

        st.markdown(f"""
        <div class="card">
            <div class="metric-label">Trade Ticket Assist</div>
            <div class="dark">Current Price: <b>{round(current_market_price, 4) if "USD" in j_ticker and j_ticker not in ["BTC-USD","ETH-USD"] else round(current_market_price, 2)}</b></div>
            <div class="dark" style="margin-top:8px;">Current Signal: <b>{current_signal}</b></div>
            <div class="dark" style="margin-top:8px;">Suggested Shares: <b>{suggested_shares}</b></div>
            <div class="dark" style="margin-top:8px;">Suggested Stop: <b>{stop_val}</b></div>
            <div class="dark" style="margin-top:8px;">Suggested Target: <b>{target_val}</b></div>
        </div>
        """, unsafe_allow_html=True)

        j_price = st.number_input("Price", min_value=0.0, value=float(current_market_price), step=0.01, format="%.4f")
        j_shares = st.number_input("Shares", min_value=0.0, value=float(suggested_shares) if suggested_shares else 0.0, step=1.0, format="%.6f")
        j_fees = st.number_input("Fees", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        j_notes = st.text_area("Notes", value="", height=120)

        checklist = [
            ("Trend aligned?", current_signal in ["STRONG BUY", "BUY"] if j_action == "BUY" else True),
            ("Risk understood?", True),
            ("Position size acceptable?", True),
            ("Reason selected?", j_reason != ""),
        ]

        st.markdown("### Rules Checklist")
        for label, ok in checklist:
            st.markdown(f"- {'✅' if ok else '⚠️'} {label}")

        if st.button("Add Journal Entry"):
            new_row = pd.DataFrame([{
                "Date": pd.to_datetime(j_date),
                "Ticker": j_ticker,
                "Action": j_action,
                "Reason": j_reason,
                "Price": j_price,
                "Shares": j_shares,
                "Fees": j_fees,
                "Notes": j_notes
            }])
            updated = pd.concat([journal, new_row], ignore_index=True)
            save_journal(updated)
            st.success("Journal entry added. Refresh the app to update everything.")

    with table_col:
        st.markdown("### Journal Table")
        edited_journal = st.data_editor(journal, use_container_width=True, hide_index=True, num_rows="dynamic", key="journal_editor")
        if st.button("Save Journal Table"):
            save_journal(edited_journal)
            st.success("Journal saved. Refresh to update portfolio calculations.")

with tab6:
    news_col, alerts_col = st.columns([1.3, 1.0])

    with news_col:
        st.subheader("News")
        news_ticker = st.selectbox("News ticker", df_results["Ticker"].tolist(), key="news_ticker")
        news_items = get_news(news_ticker)
        if not news_items:
            st.info("No news found right now.")
        else:
            for i, item in enumerate(news_items):
                st.markdown(f"""
                <div class="card" style="margin-bottom:12px;">
                    <div class="dark" style="font-size:18px;font-weight:700;">{item['title']}</div>
                    <div class="muted" style="margin-top:6px;">{item['published']}</div>
                </div>
                """, unsafe_allow_html=True)
                st.link_button("Open Article", item["link"], key=f"news_link_{i}_{news_ticker}")

    with alerts_col:
        st.subheader("Alerts")
        history = load_alert_history()
        if not history:
            st.info("No alert history yet.")
        else:
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)

with tab7:
    st.subheader("AI Trading Assistant")
    st.caption("Ask about setup quality, portfolio exposure, journal history, or compare names.")
    client = get_openai_client()

    if client is None:
        st.warning("Add OPENAI_API_KEY in Streamlit Secrets to enable the chatbot.")
    else:
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []

        chat_ticker = st.selectbox("Chat focus ticker", df_results["Ticker"].tolist(), key="chat_ticker")
        chat_row = df_results[df_results["Ticker"] == chat_ticker].iloc[0]
        recent_notes = notes.get(chat_ticker, "")
        journal_tail = journal.tail(10).to_dict(orient="records") if not journal.empty else []

        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("Ask about a stock, crypto, signal, portfolio, or journal pattern")

        qp_cols = st.columns(4)
        quick_prompts = [
            "Explain this signal",
            "What is the risk here?",
            "Which holding is weakest?",
            "Summarize my portfolio exposure",
        ]
        for i, txt in enumerate(quick_prompts):
            if qp_cols[i].button(txt, key=f"qp_{i}"):
                prompt = txt

        if prompt:
            st.session_state.chat_messages.append({"role": "user", "content": prompt})

            summary = f"""
Ticker: {chat_row['Ticker']}
Bucket: {chat_row['Bucket']}
Price: {chat_row['Price']}
1D %: {chat_row['1D %']}
5D %: {chat_row['5D %']}
RSI: {chat_row['RSI']}
MA20: {chat_row['MA20']}
MA50: {chat_row['MA50']}
Gap %: {chat_row['Gap %']}
Signal: {chat_row['Signal']}
Score: {chat_row['Score']}
Reason: {chat_row['Reason']}
Suggested Buy: {chat_row['Suggested $']}
Suggested Shares: {chat_row['Suggested Shares']}
Stop: {chat_row['Stop']}
Target: {chat_row['Target']}
Portfolio Action: {chat_row['Portfolio Action']}
Action Note: {chat_row['Action Note']}
Portfolio Health: {health}
Recent Journal Entries: {journal_tail}
User Notes: {recent_notes}
"""

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a practical stock and crypto dashboard assistant. Use the provided dashboard, journal, and portfolio data. Be clear, concise, and grounded. Do not claim certainty about future price moves. Focus on setup quality, trend, concentration risk, and what to watch next."
                        },
                        {
                            "role": "user",
                            "content": f"Dashboard context:\n{summary}\n\nUser question:\n{prompt}"
                        }
                    ]
                )
                answer = response.choices[0].message.content
            except Exception:
                answer = "The chatbot could not respond right now. Recheck your OpenAI key in Streamlit Secrets and reboot the app."

            st.session_state.chat_messages.append({"role": "assistant", "content": answer})
            with st.chat_message("assistant"):
                st.markdown(answer)
