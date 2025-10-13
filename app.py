# app.py
import os
import time
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()
ALPHA_KEY = os.getenv("ALPHAVANTAGE_KEY")

st.set_page_config(page_title="FinTech Live Dashboard", layout="wide")

st.title("FinTech Live Dashboard — FX, Stocks & Crypto (Live)")

# ========== Sidebar: user inputs ==========
st.sidebar.header("Data selection")
data_type = st.sidebar.selectbox("Choose data", ["FX (USD/EUR)", "Stock (AAPL)", "Crypto (BTC)"])
period = st.sidebar.selectbox("Period", ["1day", "5day", "30day"], index=1)

# helper: convert period to params
period_to_points = {"1day": 1, "5day": 5, "30day": 30}

# ========== FX via Alpha Vantage ==========
def fetch_fx_usd_eur():
    # Alpha Vantage FX endpoint (daily)
    url = "https://www.alphavantage.co/query"
    params = {"function": "FX_DAILY", "from_symbol": "USD", "to_symbol": "EUR",
              "outputsize": "compact", "apikey": ALPHA_KEY}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    series = data.get("Time Series FX (Daily)", {})
    df = pd.DataFrame.from_dict(series, orient="index").sort_index()
    df = df.rename(columns={
        "1. open":"open","2. high":"high","3. low":"low","4. close":"close"
    }).astype(float)
    df.index = pd.to_datetime(df.index)
    return df

# ========== Stock via Alpha Vantage ==========
def fetch_stock_intraday(symbol="AAPL"):
    url = "https://www.alphavantage.co/query"
    params = {"function": "TIME_SERIES_INTRADAY", "symbol": symbol,
              "interval": "60min", "outputsize": "compact", "apikey": ALPHA_KEY}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    key = next((k for k in data.keys() if "Time Series" in k), None)
    if not key:
        return pd.DataFrame()
    series = data[key]
    df = pd.DataFrame.from_dict(series, orient="index").sort_index()
    df = df.rename(columns=lambda c: c.split(". ")[1]).astype(float)
    df.index = pd.to_datetime(df.index)
    return df

# ========== Crypto via CoinGecko ==========
def fetch_crypto_price(coin_id="bitcoin", vs_currency="usd"):
    url = f"https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": vs_currency, "ids": coin_id, "order":"market_cap_desc", "per_page":1, "page":1}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if not data:
        return pd.DataFrame()
    # minimal: fetch market data for the last 30 days via market_chart
    cid = coin_id
    history_url = f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart"
    hparams = {"vs_currency": vs_currency, "days": "30"}
    hr = requests.get(history_url, params=hparams, timeout=10)
    hdata = hr.json()
    prices = hdata.get("prices", [])
    df = pd.DataFrame(prices, columns=["timestamp","price"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    return df

# ========== Main rendering ==========
if data_type == "FX (USD/EUR)":
    st.subheader("USD / EUR (Daily)")
    df = fetch_fx_usd_eur()
    points = period_to_points[period]
    df_plot = df.tail(30 * points)  # last N days
    fig = px.line(df_plot, y="close", labels={"index":"date","close":"USD/EUR"})
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df_plot.tail(10))

elif data_type == "Stock (AAPL)":
    st.subheader("AAPL intraday (60min)")
    df = fetch_stock_intraday("AAPL")
    if df.empty:
        st.error("Alpha Vantage rate limit or no data returned. Try again soon.")
    else:
        fig = px.line(df, y="close", labels={"index":"datetime","close":"AAPL close"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df.head(10))

else:  # Crypto BTC
    st.subheader("Bitcoin price (30-day history)")
    df = fetch_crypto_price("bitcoin", "usd")
    fig = px.line(df, y="price", labels={"index":"date","price":"BTC (USD)"})
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df.tail(10))

# Footer: refresh
st.write("Last updated:", pd.Timestamp.utcnow())
