import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from ta.volatility import BollingerBands
from ta.trend import SMAIndicator, IchimokuIndicator
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
    # returns list of dicts; each has id, symbol, name, current_price, market_cap etc. :contentReference[oaicite:1]{index=1}
    return data

@st.cache_data(ttl=600)
def fetch_coin_history(coin_id, days=30, interval="daily"):
    """Fetch historical price/volume for coin (ohlcv)"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days
    }
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    # data["prices"] = list of [timestamp_ms, price]
    # data["total_volumes"] = volumes
    df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    # optionally merge volumes
    vol = pd.DataFrame(data["total_volumes"], columns=["timestamp", "volume"])
    vol["timestamp"] = pd.to_datetime(vol["timestamp"], unit="ms")
    df = df.merge(vol, on="timestamp", how="left")
    return df

def compute_indicator(df, kind="SMA"):
    """Compute chosen indicator, return df with indicator column."""
    # df must have a “price” column
    if kind == "SMA":
        # simple moving average over 14 days
        sma = SMAIndicator(df["price"], window=14)
        df["SMA_14"] = sma.sma_indicator()
    elif kind == "Bollinger Bands":
        bb = BollingerBands(df["price"], window=20, window_dev=2)
        df["bb_h"] = bb.bollinger_hband()
        df["bb_l"] = bb.bollinger_lband()
        df["bb_m"] = bb.bollinger_mavg()
    elif kind == "Ichimoku":
        # ta’s IchimokuIndicator needs high, low, close; we only have price => approx
        # for demo: apply Ichimoku using price as all series
        ich = IchimokuIndicator(close=df["price"], high=df["price"], low=df["price"])
        df["tenkan"] = ich.ichimoku_conversion_line()
        df["kijun"] = ich.ichimoku_base_line()
        df["senkou_a"] = ich.ichimoku_a()
        df["senkou_b"] = ich.ichimoku_b()
    elif kind == "RSI":
        rsi = RSIIndicator(df["price"], window=14)
        df["rsi_14"] = rsi.rsi()
    return df

def compute_buy_sell_strength(df):
    """Simple logic: if price above SMA or above cloud, bullish = + value; else negative."""
    # Very naive: compare last price to 20-day SMA
    from ta.trend import SMAIndicator
    sma = SMAIndicator(df["price"], window=20)
    last = df["price"].iloc[-1]
    last_sma = sma.sma_indicator().iloc[-1]
    diff = last - last_sma
    # normalize to a scale -1 to +1
    strength = max(min(diff / last_sma, 1), -1)
    return strength

# ========== Streamlit UI ==========

st.title("Crypto Dashboard with Indicators & Strength Gauge")

# 1: fetch top coins
coins = fetch_top_coins(30)
coin_names = [f"{c['name']} ({c['symbol']})" for c in coins]
choice = st.selectbox("Choose a crypto:", coin_names)
# map back to coin ID
idx = coin_names.index(choice)
coin = coins[idx]
coin_id = coin["id"]

# 2: fetch its history
df = fetch_coin_history(coin_id, days=30)

# 3: choose indicator
indicator = st.selectbox("Choose indicator:", ["SMA", "Bollinger Bands", "Ichimoku", "RSI"])
df2 = compute_indicator(df.copy(), indicator)

# 4: plot price + indicator
import plotly.express as px
fig = px.line(df2, x="timestamp", y="price", title=f"{choice} Price & {indicator}")
# overlay indicator
if indicator == "SMA" and "SMA_14" in df2.columns:
    fig.add_scatter(x=df2["timestamp"], y=df2["SMA_14"], name="SMA 14")
elif indicator == "Bollinger Bands":
    fig.add_scatter(x=df2["timestamp"], y=df2["bb_h"], name="BB High")
    fig.add_scatter(x=df2["timestamp"], y=df2["bb_l"], name="BB Low")
elif indicator == "Ichimoku":
    fig.add_scatter(x=df2["timestamp"], y=df2["tenkan"], name="Tenkan")
    fig.add_scatter(x=df2["timestamp"], y=df2["kijun"], name="Kijun")
    fig.add_scatter(x=df2["timestamp"], y=df2["senkou_a"], name="Senkou A")
    fig.add_scatter(x=df2["timestamp"], y=df2["senkou_b"], name="Senkou B")
elif indicator == "RSI" and "rsi_14" in df2.columns:
    # for RSI, plot as separate subplot
    fig2 = px.line(df2, x="timestamp", y="rsi_14", title=f"{choice} RSI(14)")
    st.plotly_chart(fig2, use_container_width=True)

st.plotly_chart(fig, use_container_width=True)

# 5: show coin info: market cap, etc.
st.subheader("Coin Info")
st.write("Market Cap (USD):", coin.get("market_cap"))
st.write("Current Price (USD):", coin.get("current_price"))
st.write("24h Volume:", coin.get("total_volume"))
st.write("Market Cap Rank:", coin.get("market_cap_rank"))

# 6: gauge — buy/sell strength
strength = compute_buy_sell_strength(df2)
# map strength (-1 to +1) to 0–100
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
        'threshold': {
            'line': {'color': "black", 'width': 4},
            'thickness': 0.8,
            'value': 50
        }
    },
    title={'text': "Buy / Sell Strength"}
))
st.plotly_chart(g, use_container_width=True)

# 7: transaction fee (if available)
# Note: CoinGecko does *not* reliably provide per-transaction fee data (on-chain gas) in this API.
st.subheader("Transaction / Network Fee Info")
st.write("Note: direct transaction fee data is not available via CoinGecko API.")
