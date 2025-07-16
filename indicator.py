import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from smartapi import SmartConnect
import ta
import time
import os

# --- Load credentials from environment ---
API_KEY = os.getenv("ANGEL_API_KEY")
API_SECRET = os.getenv("ANGEL_API_SECRET")
CLIENT_CODE = os.getenv("CLIENT_CODE")
TOTP = os.getenv("TOTP")
SHEET_ID = os.getenv("SHEET_ID_CRUDEOIL")

# --- Authenticate Google Sheets ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

# --- Authenticate Angel One ---
smart = SmartConnect(api_key=API_KEY)
data = smart.generateSession(client_code=CLIENT_CODE, password=API_SECRET, totp=TOTP)
feed_token = smart.getfeedToken()

# --- Read symbols ---
symbols = ["CRUDEOIL", "NATURALGAS"]
exchange = "MCX"

# --- Timeframe ---
interval = "FifteenMinute"
lookback_minutes = 100

def fetch_data(symbol):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=lookback_minutes)

    params = {
        "exchange": exchange,
        "symboltoken": smart.ltpData(exchange, symbol)["data"]["instrumenttoken"],
        "interval": interval,
        "fromdate": start_time.strftime("%Y-%m-%d %H:%M"),
        "todate": end_time.strftime("%Y-%m-%d %H:%M")
    }

    historical = smart.getCandleData(params)
    df = pd.DataFrame(historical["data"], columns=["datetime", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df

def calculate_indicators(df):
    df["EMA"] = ta.trend.ema_indicator(df["close"], window=20)
    df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["VWAP"] = ta.volume.volume_weighted_average_price(df["high"], df["low"], df["close"], df["volume"])
    return df

def generate_signal(df):
    latest = df.iloc[-1]
    if latest["close"] > latest["VWAP"] and latest["RSI"] > 50 and latest["close"] > latest["EMA"]:
        return "BUY"
    elif latest["close"] < latest["VWAP"] and latest["RSI"] < 50 and latest["close"] < latest["EMA"]:
        return "SELL"
    else:
        return "HOLD"

def update_sheet():
    for i, symbol in enumerate(symbols, start=2):
        try:
            df = fetch_data(symbol)
            df = calculate_indicators(df)
            signal = generate_signal(df)
            last = df.iloc[-1]
            sheet.update(f"A{i}", symbol)
            sheet.update(f"B{i}", round(last["close"], 2))
            sheet.update(f"C{i}", round(last["RSI"], 2))
            sheet.update(f"D{i}", round(last["EMA"], 2))
            sheet.update(f"E{i}", round(last["VWAP"], 2))
            sheet.update(f"F{i}", signal)
        except Exception as e:
            print(f"Error with {symbol}: {e}")

update_sheet()
