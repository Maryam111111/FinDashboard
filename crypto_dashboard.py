# 2: choose timeframe
timeframe = st.selectbox("Choose timeframe:", ["1 Day", "4 Hours", "Monthly"])

if timeframe == "1 Day":
    days = 1
    interval = "hourly"
elif timeframe == "4 Hours":
    # fetch 1 day, then filter last 4 hours
    days = 1
    interval = "hourly"
elif timeframe == "Monthly":
    days = 30
    interval = "daily"

# 3: fetch coin history with selected timeframe
df = fetch_coin_history(coin_id, days=days, interval=interval)

# if user selected 4 hours, filter last 4 hours only
if timeframe == "4 Hours":
    df = df[df["timestamp"] >= (df["timestamp"].max() - pd.Timedelta(hours=4))]
