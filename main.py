import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os, json, requests, random

print("🚀 Running Algo Trading Bot...")

# ✅ Send Telegram message
def send_telegram_message(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        response = requests.post(url, data=data)
        print("📤 Telegram:", response.status_code)
    else:
        print("⚠️ Telegram token/chat_id missing")

# ✅ Google Sheet Auth
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# ✅ Open Spreadsheet
sheet_id = os.environ.get("SHEET_ID")
spreadsheet = client.open_by_key(sheet_id)
all_sheets = spreadsheet.worksheets()

# ✅ Get mock indicators
def get_indicator_values(symbol):
    price = random.randint(19000, 20000)
    rsi = random.randint(10, 90)
    ema = random.randint(19000, 20000)
    oi = random.randint(100000, 500000)
    return rsi, ema, oi, price

# ✅ Signal logic
def generate_signal(rsi, ema, price):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    else:
        return "Hold"

# ✅ Process all tabs
for sheet in all_sheets:
    print(f"\n📄 Sheet: {sheet.title}")
    try:
        data = sheet.get_all_values()
        rows = data[1:]  # Skip header

        for i, row in enumerate(rows):
            symbol = row[0].strip()
            if not symbol: continue

            rsi, ema, oi, price = get_indicator_values(symbol)
            signal = generate_signal(rsi, ema, price)

            sheet.update_cell(i+2, 2, price)      # B = LTP
            sheet.update_cell(i+2, 3, rsi)        # C = RSI
            sheet.update_cell(i+2, 4, ema)        # D = EMA
            sheet.update_cell(i+2, 5, oi)         # E = OI
            sheet.update_cell(i+2, 6, "N/A")      # F = Price Action
            sheet.update_cell(i+2, 7, signal)     # G = Final Signal
            sheet.update_cell(i+2, 8, signal)     # H = Action

            print(f"✅ {symbol} → {signal} @ {price}")
            send_telegram_message(f"[{sheet.title}] {symbol}: {signal} @ {price} | RSI: {rsi}, EMA: {ema}, OI: {oi}")

    except Exception as e:
        print(f"❌ Error: {e}")

import os, json, requests, datetime
import gspread
import numpy as np
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

from smartapi import SmartConnect  # pip install smartapi-python

print("🚀 Running LIVE Algo Trading Bot...")

# ✅ Telegram Alert
def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        try:
            requests.post(url, data=data)
        except:
            pass

# ✅ Google Sheet Auth
creds_json = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

# ✅ Angel One API Auth
client_id     = os.environ.get("CLIENT_ID")
client_secret = os.environ.get("CLIENT_SECRET")
feed_token    = os.environ.get("FEED_TOKEN")
access_token  = os.environ.get("ACCESS_TOKEN")

obj = SmartConnect(api_key=client_id)
obj.feed_token = feed_token
obj.set_session(client_id, access_token)

def get_ltp(symbol):
    try:
        params = {
            "exchange": "MCX",
            "tradingsymbol": symbol,
            "symboltoken": "53968" if symbol == "CRUDEOIL" else "0",  # Update symboltoken per symbol
        }
        data = obj.ltpData(**params)
        return float(data['data']['ltp'])
    except Exception as e:
        print(f"LTP Error {symbol}: {e}")
        return 0.0

def get_ohlc(symbol, interval='FifteenMinute', days=1):
    try:
        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=days)
        data = obj.getCandleData({
            "exchange": "MCX",
            "symboltoken": "53968",  # CRUDEOIL Token (update per symbol)
            "interval": interval,
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M")
        })
        candles = data['data']
        df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume"])
        return df
    except Exception as e:
        print(f"OHLC Error {symbol}: {e}")
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2)

def calculate_ema(series, period=14):
    ema = series.ewm(span=period, adjust=False).mean()
    return round(ema.iloc[-1], 2)

def generate_signal(rsi, ema, price):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    else:
        return "Hold"

# ✅ Open Google Sheet
sheet_id = os.environ.get("SHEET_ID")
spreadsheet = client.open_by_key(sheet_id)
sheets = spreadsheet.worksheets()

for sheet in sheets:
    print(f"\n📄 Sheet: {sheet.title}")
    data = sheet.get_all_values()
    rows = data[1:]  # Skip headers

    for i, row in enumerate(rows):
        try:
            symbol = row[0].strip()
            if not symbol:
                continue

            # ✅ LTP + OHLC
            ltp = get_ltp(symbol)
            df = get_ohlc(symbol)

            if df.empty:
                print(f"⚠️ No candle data for {symbol}")
                continue

            rsi = calculate_rsi(df["close"])
            ema = calculate_ema(df["close"])
            oi = random.randint(100000, 500000)  # 🔁 OI dummy, update if source available
            signal = generate_signal(rsi, ema, ltp)

            # ✅ Update Sheet
            sheet.update_cell(i+2, 2, ltp)      # LTP
            sheet.update_cell(i+2, 3, rsi)      # RSI
            sheet.update_cell(i+2, 4, ema)      # EMA
            sheet.update_cell(i+2, 5, oi)       # OI
            sheet.update_cell(i+2, 6, "N/A")    # Price Action
            sheet.update_cell(i+2, 7, signal)   # Final Signal
            sheet.update_cell(i+2, 8, signal)   # Action

            print(f"✅ {symbol}: {signal} @ {ltp}")
            send_telegram(f"[{sheet.title}] {symbol}: {signal} @ {ltp} | RSI: {rsi}, EMA: {ema}, OI: {oi}")

        except Exception as e:
            print(f"❌ Error on {symbol}: {e}")

import gspread
import pandas as pd
import talib
from oauth2client.service_account import ServiceAccountCredentials
from smartapi import SmartConnect

# ✅ Angel One credentials (Environment से)
client_id = os.environ.get("ANGEL_CLIENT_ID")
api_key = os.environ.get("ANGEL_API_KEY")
access_token = os.environ.get("ANGEL_ACCESS_TOKEN")

# ✅ Connect to Angel One
obj = SmartConnect(api_key=api_key)
obj.generateSession(client_id, access_token)
feed_token = obj.getfeedToken()

# ✅ Google Sheet Auth
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# ✅ Sheet & Index Tokens
sheet = client.open_by_key(os.environ.get("SHEET_ID")).sheet1
symbol_token_map = {
    "NIFTY": "99926009",
    "BANKNIFTY": "99926011",
    "FINNIFTY": "99926037",
    "MIDCPNIFTY": "99926012"
}

# ✅ Signal Logic
def generate_signal(rsi, price, ema):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    else:
        return "Hold"

# ✅ Fetch Live Price (LTP)
def get_ltp(exchange, symbol_token):
    try:
        data = {
            "exchange": exchange,
            "tradingsymbol": symbol_token,
            "symboltoken": symbol_token
        }
        res = obj.ltpData(**data)
        return float(res['data']['ltp'])
    except Exception as e:
        print("LTP Error:", e)
        return None

# ✅ Main Process
def process_sheet():
    data = sheet.get_all_values()
    rows = data[1:]  # skipping header

    for i, row in enumerate(rows):
        symbol = row[0].strip()
        token = symbol_token_map.get(symbol)

        if not token:
            continue

        ltp = get_ltp("NSE", token)
        if not ltp:
            continue

        # Simulate historical data for indicators
        prices = [ltp + i for i in range(-14, 1)]
        series = pd.Series(prices)

        rsi = round(talib.RSI(series, timeperiod=14)[-1], 2)
        ema = round(talib.EMA(series, timeperiod=14)[-1], 2)
        oi = 0  # OI for index is mostly N/A, you can leave blank or simulate
        signal = generate_signal(rsi, ltp, ema)

        # ✅ Update sheet
        sheet.update_cell(i+2, 2, ltp)      # B = LTP
        sheet.update_cell(i+2, 3, rsi)      # C = RSI
        sheet.update_cell(i+2, 4, ema)      # D = EMA
        sheet.update_cell(i+2, 5, oi)       # E = OI
        sheet.update_cell(i+2, 6, "N/A")    # F = Price Action
        sheet.update_cell(i+2, 7, signal)   # G = Final Signal
        sheet.update_cell(i+2, 8, signal)   # H = Action

        print(f"✅ {symbol} | LTP: {ltp} | RSI: {rsi} | EMA: {ema} | Signal: {signal}")

# ✅ Run it
process_sheet()
import os, json, time
import gspread
import pandas as pd
from smartapi.smartConnect import SmartConnect
from oauth2client.service_account import ServiceAccountCredentials
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

# ✅ Angel One credentials
API_KEY = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

# ✅ Google Sheet setup
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.getenv("SHEET_ID")).sheet1

# ✅ Angel One Connect
obj = SmartConnect(api_key=API_KEY)
obj.generateSession(CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN)

# ✅ Get token using symbol
def get_token(symbol):
    instrument = obj.searchInstrument("NSE", symbol)
    if instrument:
        return instrument[0]['token']
    return None

# ✅ Get 15-min candle and calculate RSI/EMA
def get_indicators(symbol):
    token = get_token(symbol)
    if not token:
        return None

    params = {
        "exchange": "NSE",
        "symboltoken": token,
        "interval": "FifteenMinute",
        "fromdate": "2025-07-18 09:15",
        "todate": "2025-07-19 15:30"
    }
    data = obj.getCandleData(params)
    df = pd.DataFrame(data['data'], columns=["datetime", "open", "high", "low", "close", "volume"])
    df["close"] = pd.to_numeric(df["close"])

    rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
    ema = EMAIndicator(df["close"], window=20).ema_indicator().iloc[-1]
    ltp = df["close"].iloc[-1]

    return round(rsi, 2), round(ema, 2), round(ltp, 2)

# ✅ Generate Signal
def get_signal(rsi, ema, price):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    return "Hold"

# ✅ Process sheet rows
rows = sheet.get_all_values()[1:]
for i, row in enumerate(rows):
    symbol = row[0].strip()
    if not symbol:
        continue
    try:
        rsi, ema, price = get_indicators(symbol)
        signal = get_signal(rsi, ema, price)

        sheet.update_cell(i+2, 2, price)  # B = LTP
        sheet.update_cell(i+2, 3, rsi)    # C = RSI
        sheet.update_cell(i+2, 4, ema)    # D = EMA
        sheet.update_cell(i+2, 7, signal) # G = Final Signal
        sheet.update_cell(i+2, 8, signal) # H = Action

        print(f"✅ {symbol}: {signal} @ {price} | RSI: {rsi} | EMA: {ema}")

    except Exception as e:
        print(f"❌ Error processing {symbol}: {e}")
