import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from ta.volatility import BollingerBands
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator

# ========== Helpers ==========

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
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    return data

@st.cache_data(ttl=600)
def fetch_coin_history(coin_id, days=30, interval="daily"):
    """Fetch historical price/volume for coin (ohlcv) with safety check."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": interval
    }
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    
    # Check if 'prices' exist
    if "prices" not in data or len(data["prices"]) == 0:
        st.warning(f"No historical data found for {coin_id}.")
        return pd.DataFrame(columns=["timestamp", "price", "volume"])
    
    df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    
    # Merge volumes if available
    if "total_volumes" in data:
        vol = pd.DataFrame(data["total_volumes"], columns=["timestamp", "volume"])
        vol["timestamp"] = pd.to_datetime(vol["timestamp"], unit="ms")
        df = df.merge(vol, on="timestamp", how="left")
    else:
        df["volume"] = None
    
    return df

def compute_indicator(df, kind="SMA"):
    """Compute chosen indicator and return df with indicator column."""
    if kind == "SMA":
        sma = SMAIndicator(df["price"], window=14)
        df["SMA_14"] = sma.sma_indicator()
    elif kind == "Bollinger Bands":
        bb = BollingerBands(df["price"], window=20, window_dev=2)
        df["bb_h"] = bb.bollinger_hband()
        df["bb_l"] = bb.bollinger_lband()
        df["bb_m"] = bb.bollinger_mavg()
    elif kind == "RSI":
        rsi = RSIIndicator(df["price"], window=14)
        df["rsi_14"] = rsi.rsi()
    return df

def compute_buy_sell_strength(df):
    """Naive logic: compare last price to 20-day SMA."""
    sma = SMAIndicator(df["price"], window=20)
    last = df["price"].iloc[-1]
    last_sma = sma.sma_indicator().iloc[-1]
    diff = last - last_sma
    strength = max(min(diff / last_sma, 1), -1)
    return strength

# ========== Streamlit UI ==========

st.title("Crypto Dashboard with Indicators & Strength Gauge")

# 1: timeframe selection
timeframe = st.selectbox("Choose timeframe:", ["1 Day", "Monthly"])

if timeframe == "1 Day":
    days = 1
    interval = "hourly"
elif timeframe == "Monthly":
    days = 30
    interval = "daily"

# 2: fetch top coins
coins = fetch_top_coins(30)
coins = [c for c in coins if c["id"] not in ["tether", "usd-coin", "dai", "binance-usd"]]
coin_names = [f"{c['name']} ({c['symbol']})" for c in coins]
choice = st.selectbox("Choose a crypto:", coin_names)
idx = coin_names.index(choice)
coin = coins[idx]
coin_id = coin["id"]

# 3: fetch coin history
df = fetch_coin_history(coin_id, days=days, interval=interval)

# 4: choose indicator
indicator = st.selectbox("Choose indicator:", ["SMA", "Bollinger Bands", "RSI"])
df2 = compute_indicator(df.copy(), indicator)

# 5: plot price + indicator
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

# 6: show coin info
st.subheader("Coin Info")
st.write("Market Cap (USD):", coin.get("market_cap"))
st.write("Current Price (USD):", coin.get("current_price"))
st.write("24h Volume:", coin.get("total_volume"))
st.write("Market Cap Rank:", coin.get("market_cap_rank"))

# 7: gauge — buy/sell strength
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
