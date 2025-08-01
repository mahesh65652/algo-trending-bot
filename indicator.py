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
import pandas as pd
import numpy as np

def calculate_indicators(df):
    df = df.copy()

    # Convert to datetime if not already
    df['time'] = pd.to_datetime(df['time'])

    # Sort data by time
    df = df.sort_values('time')

    # Calculate RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()

    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Calculate EMA (21)
    df['EMA'] = df['close'].ewm(span=21, adjust=False).mean()

    # Calculate VWAP
    df['TP'] = (df['high'] + df['low'] + df['close']) / 3
    df['vwap_numerator'] = df['TP'] * df['volume']
    df['vwap_denominator'] = df['volume']
    df['VWAP'] = df['vwap_numerator'].cumsum() / df['vwap_denominator'].cumsum()

    # Final Signal logic
    def get_signal(row):
        if (
            row['RSI'] > 60 and
            row['close'] > row['EMA'] and
            row['close'] > row['VWAP']
        ):
            return 'BUY'
        elif (
            row['RSI'] < 40 and
            row['close'] < row['EMA'] and
            row['close'] < row['VWAP']
        ):
            return 'SELL'
        else:
            return 'HOLD'

    df['Signal'] = df.apply(get_signal, axis=1)

     return df[['time', 'close', 'RSI', 'EMA', 'VWAP', 'Signal']]

import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from smartapi import SmartConnect
import time
import os

# --- Load credentials ---
API_KEY = os.getenv("ANGEL_API_KEY")
API_SECRET = os.getenv("ANGEL_API_SECRET")
CLIENT_CODE = os.getenv("CLIENT_CODE")
TOTP = os.getenv("TOTP")
SHEET_ID = os.getenv("SHEET_ID_CRUDEOIL")

# --- Google Sheets auth ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

# --- Angel One auth ---
smart = SmartConnect(api_key=API_KEY)
data = smart.generateSession(client_code=CLIENT_CODE, password=API_SECRET, totp=TOTP)
feed_token = smart.getfeedToken()

# --- Settings ---
symbols = ["CRUDEOIL", "NATURALGAS"]
exchange = "MCX"
interval = "FifteenMinute"
lookback_minutes = 120

# --- Fetch historical data ---
def fetch_data(symbol):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=lookback_minutes)

    token = smart.ltpData(exchange, symbol)["data"]["instrumenttoken"]
    params = {
        "exchange": exchange,
        "symboltoken": token,
        "interval": interval,
        "fromdate": start_time.strftime("%Y-%m-%d %H:%M"),
        "todate": end_time.strftime("%Y-%m-%d %H:%M")
    }

    historical = smart.getCandleData(params)
    df = pd.DataFrame(historical["data"], columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"])
    return df

# --- Calculate Indicators manually ---
def calculate_indicators(df):
    df = df.sort_values('time').copy()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # EMA 21
    df['EMA'] = df['close'].ewm(span=21, adjust=False).mean()

    # VWAP
    df['TP'] = (df['high'] + df['low'] + df['close']) / 3
    df['vwap_numerator'] = df['TP'] * df['volume']
    df['vwap_denominator'] = df['volume']
    df['VWAP'] = df['vwap_numerator'].cumsum() / df['vwap_denominator'].cumsum()

    # Final Signal
    def get_signal(row):
        if row['RSI'] > 60 and row['close'] > row['EMA'] and row['close'] > row['VWAP']:
            return 'BUY'
        elif row['RSI'] < 40 and row['close'] < row['EMA'] and row['close'] < row['VWAP']:
            return 'SELL'
        else:
            return 'HOLD'

    df['Signal'] = df.apply(get_signal, axis=1)

    return df

# --- Update Google Sheet ---
def update_sheet():
    for i, symbol in enumerate(symbols, start=2):
        try:
            df = fetch_data(symbol)
            df = calculate_indicators(df)
            last = df.iloc[-1]

            sheet.update(f"A{i}", symbol)
            sheet.update(f"B{i}", round(last["close"], 2))
            sheet.update(f"C{i}", round(last["RSI"], 2))
            sheet.update(f"D{i}", round(last["EMA"], 2))
            sheet.update(f"E{i}", round(last["VWAP"], 2))
            sheet.update(f"F{i}", last["Signal"])

            print(f"{symbol} updated.")
        except Exception as e:
            print(f"Error with {symbol}: {e}")

update_sheet()
