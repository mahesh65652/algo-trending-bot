import gspread
import pandas as pd
from smartapi import SmartConnect
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from datetime import datetime, timedelta
import time

# === 🟢 Step 1: CONFIGURATION ===

# Google Sheet credentials
GDRIVE_JSON = "credentials.json"  # Google Sheets JSON
SHEET_ID = "1xJQI1vYxPZKmX2tdsCpkMUaY2Hq08Z1ZhiEHpJEx0Dk"
SHEET_TAB = "BankNifty"

# Angel One API credentials
client_id = "your_client_id"
client_secret = "your_client_secret"
username = "your_client_id"
password = "your_password"
totp_secret = "your_totp_secret"

# === 🟢 Step 2: Connect to Google Sheet ===

gc = gspread.service_account(filename=GDRIVE_JSON)
sh = gc.open_by_key(SHEET_ID)
ws = sh.worksheet(SHEET_TAB)

header = ws.row_values(1)
symbols = ws.col_values(1)[1:]  # Skip header

# === 🟢 Step 3: Angel One Login ===

smartApi = SmartConnect(api_key=client_id)
token = smartApi.generateSession(username, password, smartApi.get_totp(totp_secret))
refreshToken = token['data']['refreshToken']
smartApi.generate_token(refreshToken)

# === 🟢 Step 4: Fetch data for each symbol ===

def fetch_candle(symbol_token):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)
    interval = "FifteenMinute"
    
    data = smartApi.getCandleData(
        interval=interval,
        token=symbol_token,
        fromdate=from_date.strftime('%Y-%m-%d %H:%M'),
        todate=to_date.strftime('%Y-%m-%d %H:%M')
    )
    return data['data']

def calculate_indicators(df):
    df['RSI'] = RSIIndicator(df['close'], window=14).rsi()
    df['EMA'] = EMAIndicator(df['close'], window=20).ema_indicator()
    return df

# === Symbol Token Mapping (Example) ===
symbol_token_map = {
    "BANKNIFTY": "260105"  # replace with actual token
}

for idx, symbol in enumerate(symbols):
    row_number = idx + 2  # Row 2 onwards

    if symbol not in symbol_token_map:
        print(f"⚠️ Token not found for: {symbol}")
        continue

    token = symbol_token_map[symbol]

    try:
        candles = fetch_candle(token)
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = calculate_indicators(df)

        latest = df.iloc[-1]
        ltp = latest["close"]
        rsi = round(latest["RSI"], 2)
        ema = round(latest["EMA"], 2)

        ws.update_cell(row_number, 2, ltp)
        ws.update_cell(row_number, 3, rsi)
        ws.update_cell(row_number, 4, ema)
        ws.update_cell(row_number, 5, "—")  # OI placeholder

        print(f"✅ {symbol}: LTP={ltp}, RSI={rsi}, EMA={ema}")
    except Exception as e:
        print(f"❌ Error for {symbol}: {e}")
