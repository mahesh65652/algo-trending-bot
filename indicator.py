import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import ta
from smartapi import SmartConnect
import datetime

# === CONFIGURATION ===
sheet_id = "1kdV2U3PUIN5MVsGVgoEX7up384Vvm2ap"  # Google Sheet ID
sheet_names = ["CRUDEOIL", "NG"]
api_key = "YOUR_API_KEY"
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"
refresh_token = "YOUR_REFRESH_TOKEN"
feed_token = "YOUR_FEED_TOKEN"  # Optional for live feed
access_token = "YOUR_ACCESS_TOKEN"

# === GOOGLE SHEET SETUP ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("your_json_key.json", scope)
client = gspread.authorize(creds)

# === ANGEL ONE SETUP ===
obj = SmartConnect(api_key=api_key)
obj.generateSession(client_id, refresh_token)
# fetch_token = obj.getfeedToken()

def fetch_ohlc(symbol_token, exchange, interval="FifteenMin", days=20):
    now = datetime.datetime.now()
    from_dt = now - datetime.timedelta(days=days)
    to_dt = now
    params = {
        "exchange": exchange,
        "symboltoken": symbol_token,
        "interval": interval,
        "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
        "todate": to_dt.strftime("%Y-%m-%d %H:%M")
    }
    response = obj.getCandleData(params)
    data = pd.DataFrame(response["data"], columns=["datetime", "open", "high", "low", "close", "volume"])
    return data

def calculate_indicators(df):
    df["RSI"] = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi()
    df["EMA"] = ta.trend.EMAIndicator(close=df["close"], window=20).ema_indicator()
    return df

def generate_signal(row):
    if row["RSI"] < 30 and row["close"] > row["EMA"]:
        return "BUY"
    elif row["RSI"] > 70 and row["close"] < row["EMA"]:
        return "SELL"
    else:
        return "HOLD"

def updateSheet(symbol, token, exchange):
    sheet = client.open_by_key(sheet_id).worksheet(symbol)
    df = fetch_ohlc(token, exchange)
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    signal = generate_signal(latest)

    values = [
        symbol,
        latest["close"],
        round(latest["RSI"], 2),
        round(latest["EMA"], 2),
        "Manual OI",     # Optional: Fill OI manually
        "Price Logic",   # Placeholder for price action logic
        signal,
        signal
    ]
    sheet.append_row(values, value_input_option="USER_ENTERED")

# CRUDEOIL & NG tokens (update if needed)
symbol_map = {
    "CRUDEOIL": {"token": "236", "exchange": "MCX"},
    "NG": {"token": "229", "exchange": "MCX"}
}

for symbol, info in symbol_map.items():
    updateSheet(symbol, info["token"], info["exchange"])
