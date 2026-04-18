import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from collections import Counter

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

st.set_page_config(page_title="Trading Terminal Supreme", page_icon="📈", layout="wide")

st.markdown("""
<style>
:root {
    --bg: #eef4fb;
    --bg2: #f6f9fd;
    --card: #ffffff;
    --card-soft: #f8fbff;
    --text: #0f172a;
    --muted: #475569;
    --line: rgba(148, 163, 184, 0.24);
    --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}
.stApp {
    background: linear-gradient(180deg, var(--bg2) 0%, var(--bg) 40%, #e8f0fa 100%);
}
.block-container {
    padding-top: 1rem;
    padding-bottom: 2.5rem;
    max-width: 1700px;
}
.hero {
    background: linear-gradient(135deg, #ffffff 0%, #eff6ff 40%, #f5f3ff 100%);
    border: 1px solid var(--line);
    border-radius: 28px;
    padding: 30px 34px;
    box-shadow: var(--shadow);
    margin-bottom: 18px;
}
.metric-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 24px;
    padding: 20px;
    min-height: 118px;
    box-shadow: var(--shadow);
}
.metric-label {
    color: var(--muted) !important;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
    font-weight: 700;
}
.metric-value {
    color: var(--text) !important;
    font-size: 38px;
    font-weight: 800;
    line-height: 1;
}
.card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 24px;
    padding: 20px;
    box-shadow: var(--shadow);
}
.card-soft {
    background: var(--card-soft);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 16px;
    box-shadow: var(--shadow);
}
.brief-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 24px;
    padding: 20px;
    box-shadow: var(--shadow);
}
.brief-title {
    color: var(--text) !important;
    font-size: 20px;
    font-weight: 800;
    margin-bottom: 12px;
}
.brief-row {
    color: var(--text) !important;
    background: #eef2ff;
    border-radius: 14px;
    padding: 12px 14px;
    margin-bottom: 10px;
    font-weight: 600;
}
.brief-row:nth-child(even) {
    background: #f8fbff;
}
.attention-row {
    color: var(--text) !important;
    background: #fff7ed;
    border-left: 4px solid #f97316;
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 10px;
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
.dark { color: var(--text) !important; }
.muted { color: var(--muted) !important; }
.big-ticker {
    color: var(--text) !important;
    font-size: 34px;
    font-weight: 800;
    line-height: 1;
}
.kicker {
    color: #4f46e5 !important;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 800;
}
.focus-ribbon {
    background: linear-gradient(90deg, #dbeafe 0%, #ede9fe 100%);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 10px 14px;
    color: var(--text) !important;
    font-weight: 700;
}
.empty-state {
    background: #ffffff;
    border: 1px dashed rgba(148, 163, 184, 0.45);
    border-radius: 18px;
    padding: 18px;
    color: var(--text) !important;
}
.insight-chip {
    display:inline-block;
    padding:6px 10px;
    margin:0 8px 8px 0;
    border-radius:999px;
    background:#eff6ff;
    color:#0f172a !important;
    font-weight:700;
    font-size:12px;
    border:1px solid rgba(148,163,184,0.25);
}
.position-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 18px;
    box-shadow: var(--shadow);
    margin-bottom: 12px;
}
div[data-baseweb="select"] * { color: #000000 !important; }
div[data-baseweb="select"] { background: white !important; border-radius: 10px !important; }
div[data-testid="stDataEditor"] * { color: #000000 !important; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
}
[data-testid="stDataFrame"] * { color: #000000 !important; }
.stTabs [data-baseweb="tab"] * { color: #000000 !important; }
.stTabs [role="tab"][aria-selected="true"] {
    background: white !important;
    border-radius: 12px 12px 0 0 !important;
}
button[kind="secondary"] { border-radius: 12px !important; }
</style>
""", unsafe_allow_html=True)

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
        pd.DataFrame(columns=["Date","Ticker","Action","Reason","Price","Shares","Fees","Notes"]).to_csv(JOURNAL_FILE, index=False)

def load_journal():
    ensure_journal_file()
    df = pd.read_csv(JOURNAL_FILE)
    if df.empty:
        return pd.DataFrame(columns=["Date","Ticker","Action","Reason","Price","Shares","Fees","Notes"])
    for col in ["Price","Shares","Fees"]:
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

def signal_color(signal):
    return {
        "STRONG BUY": "#15803d",
        "BUY": "#16a34a",
        "HOLD": "#2563eb",
        "WAIT": "#d97706",
        "ERROR": "#dc2626",
        "REDUCE": "#dc2626",
        "REVIEW": "#f97316",
        "NO POSITION": "#64748b",
    }.get(signal, "#64748b")

def bucket_color(bucket):
    return {
        "Long Term": "#2563eb",
        "Aggressive": "#f97316",
        "Speculative": "#7c3aed",
        "Crypto": "#0f766e",
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

def show_empty_state(title, body, next_step):
    st.markdown(f"""
    <div class="empty-state">
        <div class="dark" style="font-size:18px;font-weight:800;">{title}</div>
        <div class="muted" style="margin-top:8px;">{body}</div>
        <div class="muted" style="margin-top:10px;"><b>Next step:</b> {next_step}</div>
    </div>
    """, unsafe_allow_html=True)

def insight_chips(row):
    chips = []
    if row["Signal"] == "STRONG BUY":
        chips.append("High-conviction setup")
    if row["Signal"] == "BUY":
        chips.append("Trend intact")
    if row["Signal"] == "WAIT":
        chips.append("Overextended")
    if pd.notna(row["RSI"]) and row["RSI"] < 45:
        chips.append("Cooled off")
    if pd.notna(row["Gap %"]) and row["Gap %"] > 6:
        chips.append("Stretched above trend")
    if pd.notna(row["Gap %"]) and row["Gap %"] < -2:
        chips.append("Below short trend")
    if row["Bucket"] == "Crypto":
        chips.append("Higher volatility")
    if row["Bucket"] in ["Speculative", "Aggressive"]:
        chips.append("Risk-on profile")
    if row["Portfolio Action"] in ["REDUCE", "REVIEW"]:
        chips.append("Needs attention")
    return chips[:5]

@st.cache_data(ttl=300)
def get_data(ticker):
    df = yf.download(ticker, period="6mo", interval="1d", auto_adjust=True, progress=False)
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
    valid = clean.dropna(subset=["close","rsi","ma20","ma50"])
    return None if valid.empty else clean

def score_signal(df):
    valid = df.dropna(subset=["close","rsi","ma20","ma50"])
    latest = valid.iloc[-1]
    close = float(latest["close"]); ma20 = float(latest["ma20"]); ma50 = float(latest["ma50"]); rsi = float(latest["rsi"])
    gap = ((close / ma20) - 1) * 100
    score = 0; reasons = []
    if close > ma20:
        score += 25; reasons.append("Above MA20")
    else:
        reasons.append("Below MA20")
    if ma20 > ma50:
        score += 25; reasons.append("MA20 above MA50")
    else:
        reasons.append("MA20 below MA50")
    if 45 <= rsi <= 68:
        score += 25; reasons.append("RSI healthy")
    elif rsi < 45:
        score += 15; reasons.append("RSI cooled off")
    else:
        reasons.append("RSI high")
    if -2 <= gap <= 5:
        score += 25; reasons.append("Good entry distance")
    elif gap < -2:
        score += 10; reasons.append("Below short trend")
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
        allocation_pct = 0.15; stop_pct = 0.10; target_pct = 0.20
    elif bucket == "Crypto":
        allocation_pct = 0.10; stop_pct = 0.12; target_pct = 0.22
    elif bucket == "Speculative":
        allocation_pct = 0.10; stop_pct = 0.12; target_pct = 0.20
    else:
        allocation_pct = 0.25; stop_pct = 0.08; target_pct = 0.15
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

def analyze_journal(journal, price_lookup):
    positions = {}
    realized_rows = []
    if journal.empty:
        portfolio_df = pd.DataFrame(columns=["Ticker","Bucket","Shares Owned","Avg Cost","Current Price","Cost Basis","Market Value","Unrealized P/L"])
        realized_df = pd.DataFrame(columns=["Date","Ticker","Action","Reason","Sell Price","Shares","Realized P/L","Notes"])
        return portfolio_df, realized_df
    work = journal.dropna(subset=["Date"]).sort_values("Date", kind="stable")
    for _, row in work.iterrows():
        ticker = row["Ticker"]; action = str(row["Action"]).upper(); reason = row["Reason"]
        shares = float(row["Shares"]); price = float(row["Price"]); fees = float(row["Fees"]); notes = row["Notes"]
        if ticker not in positions:
            positions[ticker] = {"shares":0.0, "cost_basis_total":0.0}
        pos = positions[ticker]
        if action == "BUY":
            pos["shares"] += shares
            pos["cost_basis_total"] += (shares * price) + fees
        elif action == "SELL":
            if pos["shares"] <= 0:
                continue
            avg_cost = pos["cost_basis_total"] / pos["shares"] if pos["shares"] else 0
            sell_shares = min(shares, pos["shares"])
            realized = ((price - avg_cost) * sell_shares) - fees
            realized_rows.append({"Date": row["Date"], "Ticker": ticker, "Action": action, "Reason": reason, "Sell Price": price, "Shares": sell_shares, "Realized P/L": round(realized, 2), "Notes": notes})
            pos["shares"] -= sell_shares
            pos["cost_basis_total"] -= avg_cost * sell_shares
            pos["cost_basis_total"] = max(pos["cost_basis_total"], 0)
    port_rows = []
    for ticker, pos in positions.items():
        shares_owned = round(pos["shares"], 6)
        if shares_owned <= 0:
            continue
        current_price = price_lookup.get(ticker, 0)
        cost_basis = round(pos["cost_basis_total"], 2)
        avg_cost = round(cost_basis / shares_owned, 4) if shares_owned else 0
        market_value = round(current_price * shares_owned, 2)
        unrealized = round(market_value - cost_basis, 2)
        port_rows.append({"Ticker": ticker, "Bucket": BUCKETS.get(ticker, "Other"), "Shares Owned": shares_owned, "Avg Cost": avg_cost, "Current Price": round(current_price, 4) if "USD" in ticker and ticker not in ["BTC-USD", "ETH-USD"] else round(current_price, 2), "Cost Basis": cost_basis, "Market Value": market_value, "Unrealized P/L": unrealized})
    portfolio_df = pd.DataFrame(port_rows).sort_values("Market Value", ascending=False).reset_index(drop=True) if port_rows else pd.DataFrame(columns=["Ticker","Bucket","Shares Owned","Avg Cost","Current Price","Cost Basis","Market Value","Unrealized P/L"])
    realized_df = pd.DataFrame(realized_rows)
    return portfolio_df, realized_df

def build_performance_series(journal, price_lookup):
    if journal.empty:
        return pd.DataFrame(columns=["Date","Invested Capital","Current Value"])
    dates = sorted(pd.to_datetime(journal["Date"], errors="coerce").dropna().dt.date.unique())
    rows = []
    for d in dates:
        subset = journal[pd.to_datetime(journal["Date"], errors="coerce").dt.date <= d].copy()
        temp_port, _ = analyze_journal(subset, price_lookup)
        invested = float(temp_port["Cost Basis"].sum()) if not temp_port.empty else 0.0
        current = float(temp_port["Market Value"].sum()) if not temp_port.empty else 0.0
        rows.append({"Date": pd.to_datetime(d), "Invested Capital": round(invested,2), "Current Value": round(current,2)})
    return pd.DataFrame(rows)

def build_portfolio_health(portfolio_df):
    if portfolio_df.empty:
        return {"score":"No Positions","concentration":0,"crypto_pct":0,"spec_pct":0,"top_ticker":"N/A","risk_note":"Add trades in Journal to build a portfolio."}
    total_value = portfolio_df["Market Value"].sum()
    by_ticker = portfolio_df.sort_values("Market Value", ascending=False)
    top_ticker = by_ticker.iloc[0]["Ticker"]
    concentration = round((by_ticker.iloc[0]["Market Value"] / total_value) * 100, 1) if total_value > 0 else 0
    crypto_value = portfolio_df[portfolio_df["Bucket"] == "Crypto"]["Market Value"].sum()
    spec_value = portfolio_df[portfolio_df["Bucket"].isin(["Speculative","Aggressive"])]["Market Value"].sum()
    crypto_pct = round((crypto_value / total_value) * 100, 1) if total_value > 0 else 0
    spec_pct = round((spec_value / total_value) * 100, 1) if total_value > 0 else 0
    if concentration > 40 or crypto_pct > 40 or spec_pct > 55:
        score = "Overextended"; note = "High concentration or aggressive exposure."
    elif concentration > 28 or crypto_pct > 25 or spec_pct > 40:
        score = "Aggressive"; note = "Portfolio is leaning risk-on."
    elif concentration > 20:
        score = "Balanced"; note = "Reasonable but watch concentration."
    else:
        score = "Stable"; note = "Diversification looks healthy."
    return {"score":score, "concentration":concentration, "crypto_pct":crypto_pct, "spec_pct":spec_pct, "top_ticker":top_ticker, "risk_note":note}

def build_journal_analytics(journal, realized_df):
    if journal.empty:
        return {"closed_trades":0,"realized_total":0.0,"win_rate":0.0,"best_trade":None,"worst_trade":None,"most_traded_ticker":"N/A","most_profitable_reason":"N/A"}
    closed = len(realized_df)
    realized_total = float(realized_df["Realized P/L"].sum()) if not realized_df.empty else 0.0
    winners = len(realized_df[realized_df["Realized P/L"] > 0]) if not realized_df.empty else 0
    win_rate = round((winners / closed) * 100, 1) if closed > 0 else 0.0
    best_trade = realized_df.sort_values("Realized P/L", ascending=False).iloc[0].to_dict() if not realized_df.empty else None
    worst_trade = realized_df.sort_values("Realized P/L").iloc[0].to_dict() if not realized_df.empty else None
    most_traded_ticker = Counter(journal["Ticker"]).most_common(1)[0][0] if not journal.empty else "N/A"
    if not realized_df.empty and "Reason" in realized_df.columns:
        reason_group = realized_df.groupby("Reason", dropna=False)["Realized P/L"].sum().sort_values(ascending=False)
        most_profitable_reason = reason_group.index[0] if not reason_group.empty else "N/A"
    else:
        most_profitable_reason = "N/A"
    return {"closed_trades":closed,"realized_total":round(realized_total,2),"win_rate":win_rate,"best_trade":best_trade,"worst_trade":worst_trade,"most_traded_ticker":most_traded_ticker,"most_profitable_reason":most_profitable_reason}

def maybe_record_alerts(results_df):
    state = load_alert_state()
    history = load_alert_history()
    for _, row in results_df.iterrows():
        ticker = row["Ticker"]
        new_signal = row["Signal"]
        old_signal = state.get(ticker)
        if old_signal is not None and old_signal != new_signal:
            history.insert(0, {"Timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), "Ticker": ticker, "From": old_signal, "To": new_signal, "Price": row["Price"], "Score": row["Score"]})
        state[ticker] = new_signal
    save_alert_state(state); save_alert_history(history)

@st.cache_data(ttl=900)
def get_news(ticker):
    symbol = ticker.replace("-USD", "")
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:6]:
            items.append({"title": entry.get("title", ""), "link": entry.get("link", ""), "published": entry.get("published", "")})
        return items
    except Exception:
        return []

def build_price_chart(df, ticker):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["close"], mode="lines", name="Close", line=dict(width=3)))
    fig.add_trace(go.Scatter(x=df.index, y=df["ma20"], mode="lines", name="MA20", line=dict(width=2)))
    fig.add_trace(go.Scatter(x=df.index, y=df["ma50"], mode="lines", name="MA50", line=dict(width=2, dash="dot")))
    fig.update_layout(title=f"{ticker} Price Trend", template="plotly_white", height=380, margin=dict(l=20,r=20,t=50,b=20), legend=dict(orientation="h"))
    return fig

def build_rsi_chart(df, ticker):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], mode="lines", name="RSI", line=dict(width=3)))
    fig.add_hline(y=70, line_dash="dash")
    fig.add_hline(y=30, line_dash="dash")
    fig.update_layout(title=f"{ticker} RSI", template="plotly_white", height=270, margin=dict(l=20,r=20,t=50,b=20), showlegend=False)
    return fig

def build_score_gauge(score, ticker):
    fig = go.Figure(go.Indicator(mode="gauge+number", value=score, title={"text": f"{ticker} Setup Score"}, gauge={"axis":{"range":[0,100]}, "bar":{"thickness":0.35}, "steps":[{"range":[0,35],"color":"#fee2e2"},{"range":[35,65],"color":"#dbeafe"},{"range":[65,100],"color":"#dcfce7"}]}))
    fig.update_layout(height=250, margin=dict(l=20,r=20,t=40,b=10))
    return fig

def build_portfolio_bar(df):
    if df.empty: return None
    fig = go.Figure(go.Bar(x=df["Ticker"], y=df["Market Value"]))
    fig.update_layout(title="Portfolio Value by Ticker", template="plotly_white", height=320, margin=dict(l=20,r=20,t=50,b=20))
    return fig

def build_performance_chart(perf_df):
    if perf_df.empty: return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=perf_df["Date"], y=perf_df["Invested Capital"], mode="lines", name="Invested Capital"))
    fig.add_trace(go.Scatter(x=perf_df["Date"], y=perf_df["Current Value"], mode="lines", name="Current Value"))
    fig.update_layout(title="Invested Capital vs Current Value", template="plotly_white", height=320, margin=dict(l=20,r=20,t=50,b=20), legend=dict(orientation="h"))
    return fig

def build_allocation_pie(df, column, title):
    if df.empty: return None
    grouped = df.groupby(column, dropna=False)["Market Value"].sum().reset_index()
    fig = go.Figure(go.Pie(labels=grouped[column], values=grouped["Market Value"], hole=0.45))
    fig.update_layout(title=title, template="plotly_white", height=320, margin=dict(l=20,r=20,t=50,b=20))
    return fig

def build_realized_unrealized_chart(realized_total, unrealized_total):
    fig = go.Figure(go.Bar(x=["Realized P/L","Unrealized P/L"], y=[realized_total, unrealized_total]))
    fig.update_layout(title="Realized vs Unrealized", template="plotly_white", height=320, margin=dict(l=20,r=20,t=50,b=20))
    return fig

def build_heatmap_treemap(df):
    if df.empty: return None
    work = df.copy()
    work["size"] = work["Score"].fillna(1).clip(lower=1)
    work["color"] = work["1D %"].fillna(0)
    fig = go.Figure(go.Treemap(
        labels=work["Ticker"],
        parents=work["Bucket"],
        values=work["size"],
        textinfo="label+value",
        marker=dict(colors=work["color"], colorscale="RdYlGn", cmid=0),
        hovertemplate="<b>%{label}</b><br>Score: %{value}<br>1D %: %{color}<extra></extra>",
    ))
    fig.update_layout(title="Watchlist Heatmap", margin=dict(l=10,r=10,t=45,b=10), height=360, paper_bgcolor="white")
    return fig

notes = load_notes()
journal = load_journal()

results = []
data_map = {}
price_lookup = {}
for ticker in TICKERS:
    df = get_data(ticker)
    if df is None:
        results.append({"Ticker":ticker,"Bucket":BUCKETS.get(ticker,"Other"),"Price":None,"1D %":None,"5D %":None,"RSI":None,"MA20":None,"MA50":None,"Gap %":None,"Signal":"ERROR","Score":0,"Reason":"Not enough valid data","Suggested $":None,"Suggested Shares":None,"Stop":None,"Target":None,"R/R":None})
        continue
    data_map[ticker] = df
    signal, score, reason, gap = score_signal(df)
    valid = df.dropna(subset=["close","rsi","ma20","ma50"])
    latest = valid.iloc[-1]
    price = float(latest["close"])
    price_lookup[ticker] = price
    bucket = BUCKETS.get(ticker, "Other")
    suggested_dollars, suggested_shares, stop_price, target_price, rr = position_plan(price, bucket, 500.0)
    results.append({
        "Ticker":ticker,"Bucket":bucket,
        "Price": round(price,4) if "USD" in ticker and ticker not in ["BTC-USD","ETH-USD"] else round(price,2),
        "1D %": round(float(latest["change_1d"]),2),
        "5D %": round(float(latest["change_5d"]),2),
        "RSI": round(float(latest["rsi"]),1),
        "MA20": round(float(latest["ma20"]),4) if "USD" in ticker and ticker not in ["BTC-USD","ETH-USD"] else round(float(latest["ma20"]),2),
        "MA50": round(float(latest["ma50"]),4) if "USD" in ticker and ticker not in ["BTC-USD","ETH-USD"] else round(float(latest["ma50"]),2),
        "Gap %": round(float(gap),2),
        "Signal": signal, "Score": score, "Reason": reason,
        "Suggested $": suggested_dollars, "Suggested Shares": suggested_shares,
        "Stop": stop_price, "Target": target_price, "R/R": rr
    })
market_df = pd.DataFrame(results)

st.sidebar.header("Controls")
account_size = st.sidebar.number_input("Account Size ($)", 100.0, 100000.0, 500.0, 50.0)
refresh_seconds = st.sidebar.slider("Auto refresh (seconds)", 60, 900, 300, 30)
filter_signals = st.sidebar.multiselect("Filter signals", ["STRONG BUY","BUY","HOLD","WAIT","ERROR"], default=["STRONG BUY","BUY","HOLD","WAIT","ERROR"])
focus_mode = st.sidebar.toggle("Focus Mode", value=False)

market_df = market_df[market_df["Signal"].isin(filter_signals)].sort_values(by="Score", ascending=False).reset_index(drop=True)
portfolio_df, realized_df = analyze_journal(journal, price_lookup)
perf_df = build_performance_series(journal, price_lookup)
health = build_portfolio_health(portfolio_df)
analytics = build_journal_analytics(journal, realized_df)

portfolio_lookup = {}
if not portfolio_df.empty:
    for _, row in portfolio_df.iterrows():
        portfolio_lookup[row["Ticker"]] = row

enriched = []
for _, row in market_df.iterrows():
    t = row["Ticker"]; port = portfolio_lookup.get(t)
    shares_owned = float(port["Shares Owned"]) if port is not None else 0.0
    avg_cost = float(port["Avg Cost"]) if port is not None else 0.0
    market_value = float(port["Market Value"]) if port is not None else 0.0
    unrealized = float(port["Unrealized P/L"]) if port is not None else 0.0
    action, action_note = holding_action(row["Signal"], float(row["Price"]) if pd.notna(row["Price"]) else 0, avg_cost, float(row["Stop"]) if pd.notna(row["Stop"]) else 0, float(row["Target"]) if pd.notna(row["Target"]) else 0, float(row["RSI"]) if pd.notna(row["RSI"]) else 0)
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

if not df_results.empty:
    default_index = 0
    if "global_ticker" in st.session_state and st.session_state["global_ticker"] in df_results["Ticker"].tolist():
        default_index = df_results["Ticker"].tolist().index(st.session_state["global_ticker"])
    selected_ticker = st.sidebar.selectbox("Global Ticker Focus", df_results["Ticker"].tolist(), index=default_index, key="global_ticker")
else:
    selected_ticker = None

st.sidebar.markdown("### Focus Summary")
if selected_ticker and not df_results.empty:
    srow = df_results[df_results["Ticker"] == selected_ticker].iloc[0]
    st.sidebar.markdown(f"""
    <div class="card-soft">
        <div class="big-ticker" style="font-size:24px;">{selected_ticker}</div>
        <div class="muted">{srow['Bucket']}</div>
        <div style="margin-top:8px;"><span class="badge" style="background:{signal_color(srow['Signal'])};">{srow['Signal']}</span></div>
        <div class="dark" style="margin-top:10px;">Price: <b>{srow['Price']}</b></div>
        <div class="dark" style="margin-top:8px;">Portfolio: <b>${srow['Market Value']}</b></div>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<script>
setTimeout(function() {{
    window.location.reload();
}}, {refresh_seconds * 1000});
</script>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <div class="kicker">Final All-In Build v4</div>
    <h1 style="margin:4px 0 8px 0;font-size:52px;color:#0f172a !important;">Trading Terminal Supreme</h1>
    <p style="margin:0;font-size:18px;color:#334155 !important;">
        Cleaner light design, command center, heatmap, journal-driven portfolio, health score, signals, news, alerts, broker buttons, and AI assistant.
    </p>
</div>
""", unsafe_allow_html=True)

market_banner()
if focus_mode:
    st.markdown('<div class="focus-ribbon">Focus Mode is ON — showing your best setup, biggest risk, newest change, and today’s plan first.</div>', unsafe_allow_html=True)

def prepare_journal_ticket(action_type, ticker):
    if ticker is None or df_results.empty:
        return
    row = df_results[df_results["Ticker"] == ticker].iloc[0]
    st.session_state["journal_ticker"] = ticker
    st.session_state["journal_action"] = action_type
    st.session_state["journal_price_input"] = float(price_lookup.get(ticker, 0))
    st.session_state["journal_shares_input"] = float(row["Suggested Shares"]) if action_type == "BUY" else float(max(row["Shares Owned"], 0))
    st.session_state["journal_notes_input"] = f"Prepared from {ticker} | signal {row['Signal']} | stop {row['Stop']} | target {row['Target']}"

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Command Center","Dashboard","Scanner","Portfolio","Journal","News & Alerts","Chatbot"])

with tab1:
    st.subheader("Command Center")
    top_signal_changes = load_alert_history()[:5]
    if focus_mode:
        fc1, fc2, fc3 = st.columns(3)
        if not df_results.empty:
            top = df_results.iloc[0]
            with fc1:
                st.markdown(f'<div class="card"><div class="metric-label">Best Buy Right Now</div><div class="big-ticker">{top["Ticker"]}</div><div style="margin-top:8px;"><span class="badge" style="background:{signal_color(top["Signal"])};">{top["Signal"]}</span></div><div class="dark" style="margin-top:10px;">Score <b>{top["Score"]}</b></div></div>', unsafe_allow_html=True)
        with fc2:
            if top_signal_changes:
                a = top_signal_changes[0]
                st.markdown(f'<div class="card"><div class="metric-label">Newest Signal Change</div><div class="big-ticker">{a["Ticker"]}</div><div class="dark" style="margin-top:10px;"><b>{a["From"]}</b> → <b>{a["To"]}</b></div><div class="muted" style="margin-top:8px;">{a["Timestamp"]}</div></div>', unsafe_allow_html=True)
            else:
                show_empty_state("No recent signal changes","Once signals flip, they will appear here.","Keep auto-refresh on to capture changes.")
        with fc3:
            biggest_risk = None
            review = df_results[df_results["Portfolio Action"].isin(["REDUCE","REVIEW"])]
            if not review.empty:
                biggest_risk = review.iloc[0]
            if biggest_risk is not None:
                st.markdown(f'<div class="card"><div class="metric-label">Biggest Risk Right Now</div><div class="big-ticker">{biggest_risk["Ticker"]}</div><div style="margin-top:8px;"><span class="badge" style="background:{signal_color(biggest_risk["Portfolio Action"])};">{biggest_risk["Portfolio Action"]}</span></div><div class="muted" style="margin-top:8px;">{biggest_risk["Action Note"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="card"><div class="metric-label">Biggest Risk Right Now</div><div class="big-ticker">No major flags</div><div class="muted" style="margin-top:8px;">Current holdings are not showing urgent review alerts.</div></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.25, 1.0])
    with c1:
        if not df_results.empty:
            top = df_results.iloc[0]
            st.markdown(f'<div class="card"><div class="metric-label">Top Opportunity Right Now</div><div class="big-ticker">{top["Ticker"]}</div><div style="margin-top:8px;"><span class="badge" style="background:{signal_color(top["Signal"])};">{top["Signal"]}</span></div><div class="dark" style="margin-top:12px;">Score: <b>{top["Score"]}</b></div><div class="dark" style="margin-top:8px;">Suggested Buy: <b>${top["Suggested $"]}</b></div><div class="muted" style="margin-top:8px;">{top["Reason"]}</div></div>', unsafe_allow_html=True)

        st.markdown("### Morning Briefing")
        brief = []
        if not df_results.empty:
            strong_count = len(df_results[df_results["Signal"] == "STRONG BUY"])
            buy_count = len(df_results[df_results["Signal"] == "BUY"])
            hottest = df_results.sort_values("1D %", ascending=False).iloc[0]["Ticker"]
            weakest = df_results.sort_values("1D %").iloc[0]["Ticker"]
            top_bucket = df_results.iloc[0]["Bucket"]
            brief = [
                f"Strong Buy setups: {strong_count}",
                f"Buy setups: {buy_count}",
                f"Best 1-day mover: {hottest}",
                f"Weakest 1-day mover: {weakest}",
                f"Top setup category: {top_bucket}",
                f"Portfolio health: {health['score']}",
            ]
        briefing_html = '<div class="brief-card"><div class="brief-title">Today’s Briefing</div>'
        for item in brief:
            briefing_html += f'<div class="brief-row">{item}</div>'
        briefing_html += '</div>'
        st.markdown(briefing_html, unsafe_allow_html=True)

        st.markdown("### Today’s Plan")
        plan_items = []
        if not df_results.empty:
            top_buys = df_results[df_results["Signal"].isin(["STRONG BUY","BUY"])].head(3)["Ticker"].tolist()
            review = df_results[df_results["Portfolio Action"].isin(["REDUCE","REVIEW"])].head(2)["Ticker"].tolist()
            avoid = df_results[df_results["Signal"] == "WAIT"].head(2)["Ticker"].tolist()
            if top_buys:
                plan_items.append(f"Watch these setups: {', '.join(top_buys)}")
            if review:
                plan_items.append(f"Review these holdings: {', '.join(review)}")
            if avoid:
                plan_items.append(f"Avoid stretched names: {', '.join(avoid)}")
        if not plan_items:
            show_empty_state("No plan generated yet","The app will build a plan when it has active setup and portfolio data.","Add journal entries and keep your watchlist active.")
        else:
            html = '<div class="card">'
            for item in plan_items:
                html += f'<div class="brief-row">{item}</div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

        client = get_openai_client()
        if client is not None and st.button("Generate AI Morning Recap"):
            recap_context = f"Top setups: {df_results.head(5).to_dict(orient='records')}; Portfolio health: {health}; Analytics: {analytics}"
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role":"system","content":"You are a concise trading dashboard assistant. Write a short morning recap with the most important things to watch today."},
                        {"role":"user","content":recap_context}
                    ]
                )
                st.markdown("### AI Morning Recap")
                st.markdown(response.choices[0].message.content)
            except Exception:
                st.warning("AI recap unavailable right now.")

    with c2:
        st.markdown(f'<div class="card"><div class="metric-label">Portfolio Health</div><div class="big-ticker">{health["score"]}</div><div class="dark" style="margin-top:10px;">Top concentration: <b>{health["concentration"]}%</b></div><div class="dark" style="margin-top:8px;">Crypto exposure: <b>{health["crypto_pct"]}%</b></div><div class="dark" style="margin-top:8px;">Aggressive/Spec exposure: <b>{health["spec_pct"]}%</b></div><div class="dark" style="margin-top:8px;">Largest position: <b>{health["top_ticker"]}</b></div><div class="muted" style="margin-top:10px;">{health["risk_note"]}</div></div>', unsafe_allow_html=True)

        st.markdown("### Attention Needed")
        attention = []
        if health["concentration"] > 35:
            attention.append(f"Concentration risk is high in {health['top_ticker']} at {health['concentration']}%.")
        if health["crypto_pct"] > 35:
            attention.append(f"Crypto exposure is elevated at {health['crypto_pct']}%.")
        if not df_results.empty:
            review = df_results[df_results["Portfolio Action"].isin(["REDUCE","REVIEW"])]
            if not review.empty:
                for _, r in review.head(3).iterrows():
                    attention.append(f"{r['Ticker']} needs attention: {r['Portfolio Action']} — {r['Action Note']}")
        if top_signal_changes:
            first = top_signal_changes[0]
            attention.append(f"Latest signal change: {first['Ticker']} moved {first['From']} → {first['To']}.")
        if not attention:
            show_empty_state("No urgent flags","Nothing is currently triggering a high-priority review.","Check back after the next refresh or market move.")
        else:
            html = ""
            for item in attention:
                html += f'<div class="attention-row">{item}</div>'
            st.markdown(html, unsafe_allow_html=True)

with tab2:
    cols = st.columns(6)
    metrics = [("Watchlist", len(df_results)), ("Strong Buy", len(df_results[df_results["Signal"]=="STRONG BUY"])), ("Buy", len(df_results[df_results["Signal"]=="BUY"])), ("Hold", len(df_results[df_results["Signal"]=="HOLD"])), ("Portfolio $", f"{df_results['Market Value'].fillna(0).sum():,.0f}"), ("Unrealized P/L", f"{df_results['Unrealized P/L'].fillna(0).sum():,.0f}")]
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>', unsafe_allow_html=True)

    st.markdown("### Global Ticker Focus")
    if selected_ticker and not df_results.empty:
        focus_row = df_results[df_results["Ticker"] == selected_ticker].iloc[0]
        chips = insight_chips(focus_row)
        chips_html = "".join([f'<span class="insight-chip">{c}</span>' for c in chips])
        st.markdown(f'<div class="card"><div class="big-ticker">{selected_ticker}</div><div class="muted">{focus_row["Bucket"]}</div><div style="margin-top:8px;"><span class="badge" style="background:{signal_color(focus_row["Signal"])};">{focus_row["Signal"]}</span></div><div style="margin-top:12px;">{chips_html}</div></div>', unsafe_allow_html=True)
        qa1, qa2, qa3 = st.columns(3)
        with qa1:
            if st.button("Prepare Buy Ticket", key="prep_buy_btn"):
                prepare_journal_ticket("BUY", selected_ticker)
                st.success("Buy ticket prepared in Journal.")
        with qa2:
            if st.button("Prepare Sell Ticket", key="prep_sell_btn"):
                prepare_journal_ticket("SELL", selected_ticker)
                st.success("Sell ticket prepared in Journal.")
        with qa3:
            st.link_button("Open Research", yahoo_chart_url(selected_ticker), use_container_width=True)

    st.markdown("### Heatmap")
    heatmap_fig = build_heatmap_treemap(df_results)
    if heatmap_fig is not None:
        st.plotly_chart(heatmap_fig, use_container_width=True)

    st.markdown("### Detailed View")
    if selected_ticker and selected_ticker in data_map:
        row = df_results[df_results["Ticker"] == selected_ticker].iloc[0]
        df_sel = data_map[selected_ticker]
        left, mid, right = st.columns([1.05, 1.15, 2.1])
        with left:
            st.markdown(f'<div class="card"><div class="big-ticker">{selected_ticker}</div><div class="muted" style="margin-bottom:10px;">{row["Bucket"]}</div><div class="h-chip" style="background:{bucket_color(row["Bucket"])};">{row["Bucket"]}</div><div class="badge" style="background:{signal_color(row["Signal"])}; margin-top:10px;">{row["Signal"]}</div><div class="dark" style="margin-top:14px;">Price: <b>{row["Price"]}</b></div><div class="dark" style="margin-top:8px;">1D %: <b>{row["1D %"]}</b></div><div class="dark" style="margin-top:8px;">5D %: <b>{row["5D %"]}</b></div><div class="dark" style="margin-top:8px;">RSI: <b>{row["RSI"]}</b></div><div class="dark" style="margin-top:8px;">Gap %: <b>{row["Gap %"]}</b></div><div class="muted" style="margin-top:12px;">{row["Reason"]}</div></div>', unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1: st.link_button("Fidelity", fidelity_trade_url(), use_container_width=True)
            with b2: st.link_button("Robinhood", robinhood_url(), use_container_width=True)
            with b3: st.link_button("Coinbase", coinbase_url(), use_container_width=True)
        with mid:
            st.plotly_chart(build_score_gauge(row["Score"], selected_ticker), use_container_width=True)
            chips = insight_chips(row)
            chips_html = "".join([f'<span class="insight-chip">{c}</span>' for c in chips])
            st.markdown(f'<div class="card"><div class="metric-label">AI Insight Chips</div><div style="margin-top:8px;">{chips_html}</div><div class="dark" style="margin-top:10px;">Suggested Buy: <b>${row["Suggested $"]}</b></div><div class="dark" style="margin-top:8px;">Suggested Shares: <b>{row["Suggested Shares"]}</b></div><div class="dark" style="margin-top:8px;">Stop: <b>{row["Stop"]}</b></div><div class="dark" style="margin-top:8px;">Target: <b>{row["Target"]}</b></div><div class="dark" style="margin-top:8px;">R/R: <b>{row["R/R"]}</b></div></div>', unsafe_allow_html=True)
            current_note = notes.get(selected_ticker, "")
            new_note = st.text_area("Ticker Notes", value=current_note, height=120, key=f"note_{selected_ticker}")
            if st.button("Save Note", key=f"save_note_{selected_ticker}"):
                notes[selected_ticker] = new_note
                save_notes(notes)
                st.success(f"Saved note for {selected_ticker}")
        with right:
            st.plotly_chart(build_price_chart(df_sel, selected_ticker), use_container_width=True)
            st.plotly_chart(build_rsi_chart(df_sel, selected_ticker), use_container_width=True)

    with st.expander("View full watchlist table"):
        display_df = df_results.copy()
        display_df["1D Move"] = display_df["1D %"].apply(arrow_text)
        display_df["5D Move"] = display_df["5D %"].apply(arrow_text)
        st.dataframe(display_df[["Ticker","Bucket","Price","1D Move","5D Move","RSI","MA20","MA50","Gap %","Signal","Score","Suggested $","Suggested Shares","Stop","Target","R/R","Shares Owned","Avg Cost","Market Value","Unrealized P/L","Portfolio Action"]], use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Opportunity Scanner")
    c1, c2, c3, c4 = st.columns(4)
    strong_df = df_results[df_results["Signal"] == "STRONG BUY"]
    buy_df = df_results[df_results["Signal"] == "BUY"]
    cooled_df = df_results.sort_values("RSI").head(5)
    extended_df = df_results.sort_values("Gap %", ascending=False).head(5)
    with c1:
        st.markdown("#### Strong Buy")
        if strong_df.empty:
            show_empty_state("No Strong Buy setups","No names meet the strongest setup criteria right now.","Check after the next refresh.")
        else:
            for _, row in strong_df.head(4).iterrows():
                st.markdown(f'<div class="position-card"><div class="big-ticker" style="font-size:24px;">{row["Ticker"]}</div><div class="muted">{row["Bucket"]}</div><div style="margin-top:8px;"><span class="badge" style="background:{signal_color(row["Signal"])};">{row["Signal"]}</span></div><div class="dark" style="margin-top:8px;">Score <b>{row["Score"]}</b> | RSI <b>{row["RSI"]}</b></div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown("#### Buy")
        if buy_df.empty:
            show_empty_state("No Buy setups","No names currently qualify as standard buys.","Check after the next refresh.")
        else:
            for _, row in buy_df.head(4).iterrows():
                st.markdown(f'<div class="position-card"><div class="big-ticker" style="font-size:24px;">{row["Ticker"]}</div><div class="muted">{row["Bucket"]}</div><div class="dark" style="margin-top:8px;">Price <b>{row["Price"]}</b> | Score <b>{row["Score"]}</b></div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown("#### Most Cooled Off")
        st.dataframe(cooled_df[["Ticker","RSI","1D %","5D %"]], use_container_width=True, hide_index=True)
    with c4:
        st.markdown("#### Most Extended")
        st.dataframe(extended_df[["Ticker","Gap %","RSI","1D %"]], use_container_width=True, hide_index=True)

    st.markdown("### Grouped by Style")
    for bucket in ["Long Term","Aggressive","Speculative","Crypto"]:
        sub = df_results[df_results["Bucket"] == bucket]
        st.markdown(f"#### {bucket}")
        if sub.empty:
            show_empty_state(f"No {bucket} setups right now","This group has no qualifying names at the moment.","Check again after the next refresh.")
        else:
            cols = st.columns(3)
            for i, (_, row) in enumerate(sub.head(6).iterrows()):
                with cols[i % 3]:
                    st.markdown(f'<div class="position-card"><div class="big-ticker" style="font-size:22px;">{row["Ticker"]}</div><div style="margin-top:6px;"><span class="badge" style="background:{signal_color(row["Signal"])};">{row["Signal"]}</span></div><div class="dark" style="margin-top:8px;">Score <b>{row["Score"]}</b> | Price <b>{row["Price"]}</b></div></div>', unsafe_allow_html=True)

with tab4:
    st.subheader("Portfolio")
    if portfolio_df.empty:
        show_empty_state("Your portfolio is empty","This app builds your portfolio automatically from the Trade Journal.","Go to the Journal tab and add a BUY entry.")
    else:
        st.markdown("### Position Cards")
        cols = st.columns(3)
        for i, (_, row) in enumerate(portfolio_df.iterrows()):
            with cols[i % 3]:
                st.markdown(f'<div class="position-card"><div class="big-ticker" style="font-size:24px;">{row["Ticker"]}</div><div class="muted">{row["Bucket"]}</div><div class="dark" style="margin-top:8px;">Shares <b>{row["Shares Owned"]}</b></div><div class="dark" style="margin-top:6px;">Avg Cost <b>{row["Avg Cost"]}</b></div><div class="dark" style="margin-top:6px;">Market Value <b>${row["Market Value"]:,.0f}</b></div><div class="dark" style="margin-top:6px;">Unrealized <b>${row["Unrealized P/L"]:,.0f}</b></div></div>', unsafe_allow_html=True)

        largest = portfolio_df.sort_values("Market Value", ascending=False).iloc[0]
        best_unreal = portfolio_df.sort_values("Unrealized P/L", ascending=False).iloc[0]
        story_lines = [
            f"Your largest position is {largest['Ticker']} at ${largest['Market Value']:,.0f}.",
            f"You are {health['crypto_pct']}% crypto.",
            f"Your strongest unrealized position is {best_unreal['Ticker']} at ${best_unreal['Unrealized P/L']:,.0f}."
        ]
        html = '<div class="card">'
        for line in story_lines:
            html += f'<div class="brief-row">{line}</div>'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

        p1, p2 = st.columns(2)
        with p1:
            bar = build_portfolio_bar(portfolio_df)
            if bar is not None: st.plotly_chart(bar, use_container_width=True)
        with p2:
            perf = build_performance_chart(perf_df)
            if perf is not None: st.plotly_chart(perf, use_container_width=True)

        p3, p4 = st.columns(2)
        with p3:
            pie1 = build_allocation_pie(portfolio_df, "Ticker", "Allocation by Ticker")
            if pie1 is not None: st.plotly_chart(pie1, use_container_width=True)
        with p4:
            pie2 = build_allocation_pie(portfolio_df, "Bucket", "Allocation by Bucket")
            if pie2 is not None: st.plotly_chart(pie2, use_container_width=True)

        p5, p6 = st.columns(2)
        with p5:
            ru = build_realized_unrealized_chart(analytics["realized_total"], float(portfolio_df["Unrealized P/L"].sum()) if not portfolio_df.empty else 0.0)
            st.plotly_chart(ru, use_container_width=True)
        with p6:
            st.markdown(f'<div class="card"><div class="metric-label">Portfolio Health Summary</div><div class="big-ticker">{health["score"]}</div><div class="dark" style="margin-top:10px;">Top position concentration: <b>{health["concentration"]}%</b></div><div class="dark" style="margin-top:8px;">Crypto exposure: <b>{health["crypto_pct"]}%</b></div><div class="dark" style="margin-top:8px;">Spec/Aggressive exposure: <b>{health["spec_pct"]}%</b></div><div class="muted" style="margin-top:10px;">{health["risk_note"]}</div></div>', unsafe_allow_html=True)

        with st.expander("View full portfolio table"):
            st.dataframe(portfolio_df, use_container_width=True, hide_index=True)

with tab5:
    st.subheader("Trade Journal")
    st.caption("The journal is the source of truth. Portfolio and performance update from entries here.")
    form_col, table_col = st.columns([1.0, 1.35])
    with form_col:
        st.markdown("### Add Journal Entry")
        default_ticker = selected_ticker if selected_ticker else TICKERS[0]
        if "journal_ticker" not in st.session_state:
            st.session_state["journal_ticker"] = default_ticker
        if "journal_action" not in st.session_state:
            st.session_state["journal_action"] = "BUY"
        j_date = st.date_input("Date", value=datetime.today())
        j_ticker = st.selectbox("Ticker", TICKERS, key="journal_ticker")
        j_action = st.selectbox("Action", ACTIONS, key="journal_action")
        j_reason = st.selectbox("Reason", REASONS, key="journal_reason")
        current_market_price = price_lookup.get(j_ticker, 0.0)
        current_row = df_results[df_results["Ticker"] == j_ticker]
        current_signal = current_row["Signal"].iloc[0] if not current_row.empty else "N/A"
        suggested_shares = float(current_row["Suggested Shares"].iloc[0]) if not current_row.empty else 0.0
        stop_val = current_row["Stop"].iloc[0] if not current_row.empty else 0
        target_val = current_row["Target"].iloc[0] if not current_row.empty else 0
        if "journal_price_input" not in st.session_state:
            st.session_state["journal_price_input"] = float(current_market_price)
        if "journal_shares_input" not in st.session_state:
            st.session_state["journal_shares_input"] = float(suggested_shares)
        if "journal_notes_input" not in st.session_state:
            st.session_state["journal_notes_input"] = ""
        if st.button("Use Suggested Trade Plan"):
            st.session_state["journal_price_input"] = float(current_market_price)
            st.session_state["journal_shares_input"] = float(suggested_shares)
            st.session_state["journal_notes_input"] = f"Signal {current_signal}; stop {stop_val}; target {target_val}"
        st.markdown(f'<div class="card-soft"><div class="metric-label">Trade Ticket Assist</div><div class="dark">Current Price: <b>{round(current_market_price, 4) if "USD" in j_ticker and j_ticker not in ["BTC-USD","ETH-USD"] else round(current_market_price, 2)}</b></div><div class="dark" style="margin-top:8px;">Current Signal: <b>{current_signal}</b></div><div class="dark" style="margin-top:8px;">Suggested Shares: <b>{suggested_shares}</b></div><div class="dark" style="margin-top:8px;">Suggested Stop: <b>{stop_val}</b></div><div class="dark" style="margin-top:8px;">Suggested Target: <b>{target_val}</b></div></div>', unsafe_allow_html=True)
        j_price = st.number_input("Price", min_value=0.0, step=0.01, format="%.4f", key="journal_price_input")
        j_shares = st.number_input("Shares", min_value=0.0, step=1.0, format="%.6f", key="journal_shares_input")
        j_fees = st.number_input("Fees", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        j_notes = st.text_area("Notes", height=120, key="journal_notes_input")
        estimated_new_value = float(portfolio_df["MarketValue"].sum()) + (j_price * j_shares if j_action == "BUY" else 0) if "MarketValue" in portfolio_df.columns else float(portfolio_df["Market Value"].sum()) + (j_price * j_shares if j_action == "BUY" else 0)
        concentration_note = ""
        if estimated_new_value > 0 and j_action == "BUY":
            current_mv = float(portfolio_df[portfolio_df["Ticker"] == j_ticker]["Market Value"].sum()) if not portfolio_df.empty else 0.0
            new_concentration = round(((current_mv + (j_price * j_shares)) / estimated_new_value) * 100, 1)
            concentration_note = f"Estimated concentration after trade: {new_concentration}%"
        checklist = [
            ("Trend aligned?", current_signal in ["STRONG BUY","BUY"] if j_action == "BUY" else True),
            ("Risk understood?", True),
            ("Position size acceptable?", True),
            ("Reason selected?", j_reason != ""),
        ]
        st.markdown("### Rules Checklist")
        for label, ok in checklist:
            st.markdown(f"- {'✅' if ok else '⚠️'} {label}")
        if concentration_note:
            st.markdown(f"- 📌 {concentration_note}")
        if st.button("Add Journal Entry"):
            new_row = pd.DataFrame([{"Date": pd.to_datetime(j_date), "Ticker": j_ticker, "Action": j_action, "Reason": j_reason, "Price": j_price, "Shares": j_shares, "Fees": j_fees, "Notes": j_notes}])
            updated = pd.concat([journal, new_row], ignore_index=True)
            save_journal(updated)
            st.session_state["journal_price_input"] = float(current_market_price)
            st.session_state["journal_shares_input"] = 0.0
            st.session_state["journal_notes_input"] = ""
            st.success("Journal entry added. Refresh the app to update everything.")
    with table_col:
        st.markdown("### Journal Table")
        edited_journal = st.data_editor(journal, use_container_width=True, hide_index=True, num_rows="dynamic", key="journal_editor")
        if st.button("Save Journal Table"):
            save_journal(edited_journal)
            st.success("Journal saved. Refresh to update portfolio calculations.")
        st.markdown("### Journal Analytics")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Closed Trades", analytics["closed_trades"])
        a2.metric("Realized P/L", f"${analytics['realized_total']:,.0f}")
        a3.metric("Win Rate", f"{analytics['win_rate']}%")
        a4.metric("Most Traded", analytics["most_traded_ticker"])
        st.markdown(f'<div class="card"><div class="metric-label">Journal Insights</div><div class="dark">Most Profitable Reason: <b>{analytics["most_profitable_reason"]}</b></div></div>', unsafe_allow_html=True)
        if analytics["best_trade"] is not None:
            bt = analytics["best_trade"]; wt = analytics["worst_trade"]
            st.markdown(f'<div class="card"><div class="metric-label">Best vs Worst Closed Trade</div><div class="dark">Best: <b>{bt["Ticker"]}</b> | {bt["Realized P/L"]}</div><div class="dark" style="margin-top:8px;">Worst: <b>{wt["Ticker"]}</b> | {wt["Realized P/L"]}</div></div>', unsafe_allow_html=True)

with tab6:
    news_col, alerts_col = st.columns([1.3, 1.0])
    with news_col:
        st.subheader("News")
        news_ticker = selected_ticker if selected_ticker else (df_results["Ticker"].iloc[0] if not df_results.empty else None)
        if news_ticker is None:
            show_empty_state("No ticker selected","Choose a ticker from the global selector to load news.","Pick a Global Ticker Focus in the sidebar.")
        else:
            news_items = get_news(news_ticker)
            if not news_items:
                show_empty_state("No news found","There were no recent headlines returned for this ticker.","Try another name or refresh later.")
            else:
                for i, item in enumerate(news_items):
                    st.markdown(f'<div class="card" style="margin-bottom:12px;"><div class="dark" style="font-size:18px;font-weight:700;">{item["title"]}</div><div class="muted" style="margin-top:6px;">{item["published"]}</div></div>', unsafe_allow_html=True)
                    st.link_button("Open Article", item["link"], key=f"news_link_{i}_{news_ticker}")
    with alerts_col:
        st.subheader("Alerts")
        history = load_alert_history()
        if not history:
            show_empty_state("No alerts yet","Signal changes will appear here as the app detects them.","Keep auto-refresh on and let the watchlist run.")
        else:
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)

with tab7:
    st.subheader("AI Trading Assistant")
    st.caption("Ask about setup quality, portfolio exposure, journal history, or compare names.")
    client = get_openai_client()
    if client is None:
        show_empty_state("Chatbot not enabled","The AI assistant needs an OpenAI API key in Streamlit Secrets.","Add OPENAI_API_KEY and reboot the app.")
    else:
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
        chat_ticker = selected_ticker if selected_ticker else (df_results["Ticker"].iloc[0] if not df_results.empty else None)
        if chat_ticker is None:
            show_empty_state("No ticker available","The chatbot needs a ticker context.","Make sure your watchlist has data.")
        else:
            chat_row = df_results[df_results["Ticker"] == chat_ticker].iloc[0]
            recent_notes = notes.get(chat_ticker, "")
            journal_tail = journal.tail(10).to_dict(orient="records") if not journal.empty else []
            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
            prompt = st.chat_input("Ask about a stock, crypto, signal, portfolio, or journal pattern")
            qp_cols = st.columns(4)
            quick_prompts = ["Explain this signal","What is the risk here?","Which holding is weakest?","Summarize my portfolio exposure"]
            for i, txt in enumerate(quick_prompts):
                if qp_cols[i].button(txt, key=f"qp_{i}"):
                    prompt = txt
            if prompt:
                st.session_state.chat_messages.append({"role":"user","content":prompt})
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
Journal Analytics: {analytics}
"""
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role":"system","content":"You are a practical stock and crypto dashboard assistant. Use the provided dashboard, journal, and portfolio data. Be clear, concise, and grounded. Do not claim certainty about future price moves. Focus on setup quality, trend, concentration risk, and what to watch next."},
                            {"role":"user","content":f"Dashboard context:\\n{summary}\\n\\nUser question:\\n{prompt}"}
                        ]
                    )
                    answer = response.choices[0].message.content
                except Exception:
                    answer = "The chatbot could not respond right now. Recheck your OpenAI key in Streamlit Secrets and reboot the app."
                st.session_state.chat_messages.append({"role":"assistant","content":answer})
                with st.chat_message("assistant"):
                    st.markdown(answer)
