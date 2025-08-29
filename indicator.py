import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from smartapi import SmartConnect
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
# ✅ FIX: Use a more robust login method with a try-except block
try:
    data = smart.generateSession(client_code=CLIENT_CODE, password=API_SECRET, totp=TOTP)
    feed_token = smart.getfeedToken()
    print("Angel One login successful.")
except Exception as e:
    print(f"Error during Angel One login: {e}")
    exit()

# --- Settings ---
symbols = ["CRUDEOIL", "NATURALGAS"]
exchange = "MCX"
interval = "FifteenMinute"
lookback_minutes = 120

# --- Fetch historical data ---
def fetch_data(symbol):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=lookback_minutes)

    try:
        token_data = smart.ltpData(exchange, symbol)
        if 'data' not in token_data or 'instrumenttoken' not in token_data['data']:
            print(f"Error: Could not get instrumenttoken for {symbol}.")
            return None

        token = token_data['data']['instrumenttoken']
        params = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": interval,
            "fromdate": start_time.strftime("%Y-%m-%d %H:%M"),
            "todate": end_time.strftime("%Y-%m-%d %H:%M")
        }

        historical = smart.getCandleData(params)
        if 'data' not in historical:
            print(f"No historical data found for {symbol}.")
            return None
        
        df = pd.DataFrame(historical["data"], columns=["time", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"])
        return df

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

# --- Calculate Indicators manually ---
def calculate_indicators(df):
    if df is None or df.empty:
        return None

    df = df.sort_values('time').copy()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    
    # ✅ FIX: Avoid division by zero
    rs = np.where(avg_loss == 0, np.inf, avg_gain / avg_loss)
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
        # ✅ FIX: Check for NaN values before comparison
        if pd.isna(row['RSI']) or pd.isna(row['EMA']) or pd.isna(row['VWAP']):
            return 'HOLD'

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
            if df is None:
                print(f"Skipping update for {symbol} due to data fetch error.")
                continue

            df = calculate_indicators(df)
            if df is None:
                print(f"Skipping update for {symbol} due to indicator calculation error.")
                continue
            
            last = df.iloc[-1]

            sheet.update(f"A{i}", symbol)
            sheet.update(f"B{i}", round(last["close"], 2))
            sheet.update(f"C{i}", round(last["RSI"], 2))
            sheet.update(f"D{i}", round(last["EMA"], 2))
            sheet.update(f"E{i}", round(last["VWAP"], 2))
            sheet.update(f"F{i}", last["Signal"])

            print(f"{symbol} updated successfully.")
        except Exception as e:
            print(f"Error updating sheet for {symbol}: {e}")

update_sheet()
