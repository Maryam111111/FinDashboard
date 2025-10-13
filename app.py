# app.py
import os
import time
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import yfinance as yf

st.set_page_config(page_title="FinTech Live Dashboard", layout="wide")

st.title("FinTech Live Dashboard — FX, Stocks & Crypto (Live)")

# ========== Sidebar: user inputs ==========
st.sidebar.header("Data selection")
data_type = st.sidebar.selectbox("Choose data", ["FX (USD/EUR)", "Stock (AAPL)", "Crypto (BTC)"])
period = st.sidebar.selectbox("Period", ["1day", "5day", "30day"], index=1)
period_to_points = {"1day": 1, "5day": 5, "30day": 30}

# ========== Cache decorator ==========
@st.cache_data(ttl=600)
def fetch_fx_usd_eur():
    """Fetch daily USD/EUR exchange rate from ECB"""
    url = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
    headers = {"Accept": "text/csv"}
    r = requests.get(url, headers=headers, timeout=10)
    df = pd.read_csv(pd.compat.StringIO(r.text))
    df = df.rename(columns={"TIME_PERIOD": "date", "OBS_VALUE": "rate"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df

@st.cache_data(ttl=600)
def fetch_stock_yfinance(symbol="AAPL"):
    """Fetch stock data from Yahoo Finance"""
    df = yf.download(symbol, period="1mo", interval="1h", progress=False)
    df = df.reset_index()
    df.rename(columns={"Datetime": "datetime"}, inplace=True)
    return df

@st.cache_data(ttl=600)
def fetch_crypto_price(coin_id="bitcoin", vs_currency="usd"):
    """Fetch crypto price from CoinGecko"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": "30"}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    prices = data.get("prices", [])
    df = pd.DataFrame(prices, columns=["timestamp", "price"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

# ========== Main display logic ==========
if data_type == "FX (USD/EUR)":
    st.subheader("USD / EUR (ECB Reference Rate)")
    try:
        df = fetch_fx_usd_eur()
        fig = px.line(df, x="date", y="rate", title="USD/EUR Exchange Rate")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df.tail(10))
    except Exception as e:
        st.error(f"Error fetching FX data: {e}")

elif data_type == "Stock (AAPL)":
    st.subheader("AAPL — Yahoo Finance (1 Month, 1 Hour Interval)")
    try:
        df = fetch_stock_yfinance("AAPL")
        fig = px.line(df, x="datetime", y="Close", title="AAPL Stock Price (1 Month)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df.tail(10))
    except Exception as e:
        st.error(f"Error fetching stock data: {e}")

else:
    st.subheader("Bitcoin — CoinGecko (30 Days History)")
    try:
        df = fetch_crypto_price("bitcoin", "usd")
        fig = px.line(df, x="timestamp", y="price", title="Bitcoin Price (USD)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df.tail(10))
    except Exception as e:
        st.error(f"Error fetching crypto data: {e}")

# Footer
st.write("Last updated:", pd.Timestamp.utcnow())
st.caption("Data: Yahoo Finance, CoinGecko, ECB | Dashboard by [Your Name]")
