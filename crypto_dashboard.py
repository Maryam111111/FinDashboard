import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from ta.volatility import BollingerBands
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator

# ===== Helpers =====

@st.cache_data(ttl=600)
def fetch_top_coins(n=30):
    """Fetch top n cryptos by market cap via CoinGecko."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": n,
        "page": 1,
        "sparkline": False
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if isinstance(data, list):
            return data
        else:
            return []
    except:
        return []

@st.cache_data(ttl=600)
def fetch_coin_history(coin_id, days=30, interval="daily"):
    """Fetch historical price/volume for coin (ohlcv) with safety check."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": interval
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "prices" not in data or len(data["prices"]) == 0:
            st.warning(f"No historical data found for {coin_id}.")
            return pd.DataFrame(columns=["timestamp", "price", "volume"])
        df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        if "total_volumes" in data:
            vol = pd.DataFrame(data["total_volumes"], columns=["timestamp", "volume"])
            vol["timestamp"] = pd.to_datetime(vol["timestamp"], unit="ms")
            df = df.merge(vol, on="timestamp", how="left")
        else:
            df["volume"] = None
        return df
    except:
        st.warning("Failed to fetch historical data.")
        return pd.DataFrame(columns=["timestamp", "price", "volume"])

def compute_indicator(df, kind="SMA"):
    """Compute chosen indicator and return df with indicator column."""
    if kind == "SMA":
        sma = SMAIndicator(df["price"], window=50)
        df["SMA_14"] = sma.sma_indicator()
    elif kind == "Bollinger Bands":
        bb = BollingerBands(df["price"], window=50, window_dev=2)
        df["bb_h"] = bb.bollinger_hband()
        df["bb_l"] = bb.bollinger_lband()
        df["bb_m"] = bb.bollinger_mavg()
    elif kind == "RSI":
        rsi = RSIIndicator(df["price"], window=50)
        df["rsi_14"] = rsi.rsi()
    return df

def compute_buy_sell_strength(df):
    """Naive logic: compare last price to 20-day SMA."""
    if df.empty:
        return 0
    sma = SMAIndicator(df["price"], window=20)
    last = df["price"].iloc[-1]
    last_sma = sma.sma_indicator().iloc[-1]
    diff = last - last_sma
    strength = max(min(diff / last_sma, 1), -1)
    return strength

# ===== Streamlit UI =====

st.title("Crypto Dashboard with Indicators & Strength Gauge")

# 1: fetch top coins
coins_raw = fetch_top_coins(30)
if not coins_raw:
    st.error("Failed to fetch top coins. Try again later.")
    st.stop()

coins = [c for c in coins_raw if c.get("id") not in ["tether", "usd-coin", "dai", "binance-usd"]]
if not coins:
    st.error("No coins available.")
    st.stop()

coin_names = [f"{c.get('name','')} ({c.get('symbol','')})" for c in coins]
choice = st.selectbox("Choose a crypto:", coin_names)
idx = coin_names.index(choice)
coin = coins[idx]
coin_id = coin.get("id")

# 2: fetch coin history (hardcoded monthly)
df = fetch_coin_history(coin_id, days=30, interval="daily")
if df.empty:
    st.error("No historical data available for this coin.")
    st.stop()

# 3: choose indicator
indicator = st.selectbox("Choose indicator:", ["SMA", "Bollinger Bands", "RSI"])
df2 = compute_indicator(df.copy(), indicator)

# 4: plot price + indicator
fig = px.line(df2, x="timestamp", y="price", title=f"{choice} Price & {indicator}")
if indicator == "SMA" and "SMA_14" in df2.columns:
    fig.add_scatter(x=df2["timestamp"], y=df2["SMA_14"], name="SMA 14")
elif indicator == "Bollinger Bands":
    fig.add_scatter(x=df2["timestamp"], y=df2["bb_h"], name="BB High")
    fig.add_scatter(x=df2["timestamp"], y=df2["bb_l"], name="BB Low")
elif indicator == "RSI" and "rsi_14" in df2.columns:
    fig2 = px.line(df2, x="timestamp", y=df2["rsi_14"], title=f"{choice} RSI(14)")
    st.plotly_chart(fig2, use_container_width=True)

st.plotly_chart(fig, use_container_width=True)

# 5: show coin info
st.subheader("Coin Info")
st.write("Market Cap (USD):", coin.get("market_cap"))
st.write("Current Price (USD):", coin.get("current_price"))
st.write("24h Volume:", coin.get("total_volume"))
st.write("Market Cap Rank:", coin.get("market_cap_rank"))

# 6: gauge — buy/sell strength
strength = compute_buy_sell_strength(df2)
perc = int((strength + 1) * 50)
g = go.Figure(go.Indicator(
    mode="gauge+number",
    value=perc,
    domain={'x': [0, 1], 'y': [0, 1]},
    gauge={
        'axis': {'range': [0, 100]},
        'bar': {'color': "darkblue"},
        'steps': [
            {'range': [0, 50], 'color': "red"},
            {'range': [50, 100], 'color': "green"}
        ],
        'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.8, 'value': 50}
    },
    title={'text': "Buy / Sell Strength"}
))
st.plotly_chart(g, use_container_width=True)
