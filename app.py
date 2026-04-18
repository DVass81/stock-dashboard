import streamlit as st
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator

st.set_page_config(layout="wide")

st.title("📈 Stock Dashboard")

tickers = ["NVDA", "MSFT", "AMZN", "GOOGL", "SOUN", "RGTI", "PLUG"]

def get_data(ticker):
    df = yf.download(ticker, period="3mo", interval="1d")

    if df.empty:
        return None

    close = df["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.squeeze()

    close = pd.to_numeric(close, errors="coerce")

    df["close"] = close
    df["rsi"] = RSIIndicator(close=close).rsi()
    df["ma20"] = close.rolling(20).mean()
    df["ma50"] = close.rolling(50).mean()

    return df

def get_signal(df):
    valid = df.dropna(subset=["close", "rsi", "ma20", "ma50"])

    if valid.empty:
        return "WAIT"

    latest = valid.iloc[-1]

    if latest["close"] > latest["ma20"] and latest["ma20"] > latest["ma50"] and latest["rsi"] < 70:
        return "BUY"
    elif latest["rsi"] > 75:
        return "WAIT"
    else:
        return "HOLD"

results = []

for ticker in tickers:
    df = get_data(ticker)

    if df is None:
        results.append([ticker, "ERROR", None, None, None, None])
        continue

    signal = get_signal(df)

    latest = df.iloc[-1]

    results.append([
        ticker,
        signal,
        round(latest["close"], 2),
        round(latest["rsi"], 2),
        round(latest["ma20"], 2),
        round(latest["ma50"], 2)
    ])

df_results = pd.DataFrame(results, columns=["Ticker", "Signal", "Price", "RSI", "MA20", "MA50"])

col1, col2, col3, col4 = st.columns(4)

col1.metric("Watchlist", len(df_results))
col2.metric("BUY", len(df_results[df_results["Signal"] == "BUY"]))
col3.metric("HOLD", len(df_results[df_results["Signal"] == "HOLD"]))
col4.metric("WAIT", len(df_results[df_results["Signal"] == "WAIT"]))

st.dataframe(df_results)
