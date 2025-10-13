import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# ======== Helper Functions ========

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
        return r.json()
    except:
        return []

@st.cache_data(ttl=600)
def fetch_coin_history(coin_id, days=90, interval="daily"):
    """Fetch historical market data for a given coin."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": interval}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "prices" not in data:
            return pd.DataFrame()
        df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        if "total_volumes" in data:
            vol = pd.DataFrame(data["total_volumes"], columns=["timestamp", "volume"])
            vol["timestamp"] = pd.to_datetime(vol["timestamp"], unit="ms")
            df = df.merge(vol, on="timestamp", how="left")
        # Simulate high/low/close for price-type selection
        df["high"] = df["price"] * (1 + 0.02)
        df["low"] = df["price"] * (1 - 0.02)
        df["close"] = df["price"]
        df["average"] = (df["high"] + df["low"] + df["close"]) / 3
        return df
    except:
        return pd.DataFrame()

def compute_cross_ma(df, short_win=10, long_win=50, price_type="close"):
    """Compute short & long moving averages for cross-over strategy."""
    short_ma = SMAIndicator(df[price_type], window=short_win).sma_indicator()
    long_ma = SMAIndicator(df[price_type], window=long_win).sma_indicator()
    df[f"SMA_{short_win}"] = short_ma
    df[f"SMA_{long_win}"] = long_ma
    df["Signal"] = (short_ma > long_ma).astype(int)
    return df

def compute_rsi(df, window=14, price_type="close"):
    df[f"RSI_{window}"] = RSIIndicator(df[price_type], window=window).rsi()
    return df

def compute_bbands(df, window=20, price_type="close"):
    bb = BollingerBands(df[price_type], window=window, window_dev=2)
    df["bb_h"] = bb.bollinger_hband()
    df["bb_l"] = bb.bollinger_lband()
    df["bb_m"] = bb.bollinger_mavg()
    return df

# ======== Streamlit UI ========

st.title("💹 Advanced Crypto Dashboard — Cross MAs, Indicators & Oscillators")

# --- 1. Fetch Coins ---
coins = fetch_top_coins(30)
if not coins:
    st.error("⚠️ Failed to fetch top coins. Try again later.")
    st.stop()

# --- 2. Choose Coin ---
coins = [c for c in coins if c["id"] not in ["tether", "usd-coin", "dai", "binance-usd"]]
coin_names = [f"{c['name']} ({c['symbol']})" for c in coins]
choice = st.selectbox("Choose a cryptocurrency:", coin_names)
idx = coin_names.index(choice)
coin = coins[idx]
coin_id = coin["id"]

# --- 3. Fetch Data ---
days = st.slider("Select number of past days:", 30, 365, 90)
df = fetch_coin_history(coin_id, days=days)
if df.empty:
    st.error("No data available.")
    st.stop()

# --- 4. Choose Price Type ---
price_type = st.selectbox("Choose price type:", ["close", "high", "low", "average"])

# --- 5. Choose Analysis Type ---
analysis_type = st.selectbox("Select analysis type:", ["Cross Moving Averages", "RSI", "Bollinger Bands"])

# --- 6. Indicator Settings ---
if analysis_type == "Cross Moving Averages":
    short_win = st.slider("Short MA Window:", 5, 30, 10)
    long_win = st.slider("Long MA Window:", 30, 200, 50)
    df = compute_cross_ma(df, short_win, long_win, price_type)
elif analysis_type == "RSI":
    rsi_window = st.slider("RSI Window:", 7, 50, 14)
    df = compute_rsi(df, rsi_window, price_type)
elif analysis_type == "Bollinger Bands":
    bb_window = st.slider("Bollinger Band Window:", 10, 50, 20)
    df = compute_bbands(df, bb_window, price_type)

# --- 7. Visualization ---
fig = px.line(df, x="timestamp", y=df[price_type], title=f"{choice} — {analysis_type}", labels={"timestamp": "Date", price_type: "Price (USD)"})

if analysis_type == "Cross Moving Averages":
    fig.add_scatter(x=df["timestamp"], y=df[f"SMA_{short_win}"], name=f"SMA {short_win}", line=dict(dash="dot"))
    fig.add_scatter(x=df["timestamp"], y=df[f"SMA_{long_win}"], name=f"SMA {long_win}", line=dict(dash="dash"))
elif analysis_type == "Bollinger Bands":
    fig.add_scatter(x=df["timestamp"], y=df["bb_h"], name="BB High", line=dict(dash="dot"))
    fig.add_scatter(x=df["timestamp"], y=df["bb_l"], name="BB Low", line=dict(dash="dot"))
elif analysis_type == "RSI":
    fig_rsi = px.line(df, x="timestamp", y=df[f"RSI_{rsi_window}"], title=f"{choice} RSI ({rsi_window})")
    st.plotly_chart(fig_rsi, use_container_width=True)

st.plotly_chart(fig, use_container_width=True)

# --- 8. Show Coin Info ---
st.subheader("Coin Info")
st.write("💰 Current Price (USD):", coin.get("current_price"))
st.write("🏦 Market Cap (USD):", coin.get("market_cap"))
st.write("📊 24h Volume:", coin.get("total_volume"))
st.write("📈 Market Cap Rank:", coin.get("market_cap_rank"))
