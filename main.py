import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import random
import os
import json
import requests

print("🚀 Running Algo Trading Bot...")

# ✅ Telegram message function
def send_telegram_message(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        response = requests.post(url, data=data)
        print("📤 Telegram Status:", response.status_code)
    else:
        print("⚠️ Telegram token or chat ID not found in environment.")

# ✅ Google Sheet Auth
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# ✅ Open Sheet
sheet_id = os.environ.get("SHEET_ID")
spreadsheet = client.open_by_key(sheet_id)
all_sheets = spreadsheet.worksheets()

# ✅ Indicator logic
def get_indicator_values(symbol):
    rsi = random.randint(10, 90)
    ema = random.randint(19000, 20000)
    oi = random.randint(100000, 500000)
    price = random.randint(19000, 20000)
    return rsi, ema, oi, price

# ✅ Signal logic
def generate_signal(rsi, ema, price):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    else:
        return "Hold"

# ✅ Loop through all sheets (tabs)
for sheet in all_sheets:
    sheet_name = sheet.title
    print(f"\n📄 Processing Sheet: {sheet_name}")

    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        for i, row in df.iterrows():
            symbol = row.get("Symbol")
            if not symbol:
                continue

            rsi, ema, oi, price = get_indicator_values(symbol)
            signal = generate_signal(rsi, ema, price)

            sheet.update_cell(i + 2, 2, price)      # LTP
            sheet.update_cell(i + 2, 3, rsi)        # RSI
            sheet.update_cell(i + 2, 4, ema)        # EMA
            sheet.update_cell(i + 2, 5, oi)         # OI
            sheet.update_cell(i + 2, 6, "N/A")      # Price Action
            sheet.update_cell(i + 2, 7, signal)     # Final Signal
            sheet.update_cell(i + 2, 8, signal)     # Action

            send_telegram_message(f"📢 [{sheet_name}] {symbol}: {signal} @ {price} | RSI: {rsi}, EMA: {ema}, OI: {oi}")

    except Exception as e:
        print(f"❌ Error in Sheet {sheet_name}: {e}")
        
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import requests
import random

print("🚀 Running Algo Trading Bot...")

# ✅ Telegram message function
def send_telegram_message(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        response = requests.post(url, data=data)
        print("📤 Telegram Status:", response.status_code)
    else:
        print("⚠️ Telegram token or chat ID not found in environment.")

# ✅ Google Sheet Auth
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# ✅ Open Sheet
sheet_id = os.environ.get("SHEET_ID")
spreadsheet = client.open_by_key(sheet_id)
all_sheets = spreadsheet.worksheets()

# ✅ Indicator logic
def get_indicator_values(symbol):
    rsi = random.randint(10, 90)
    ema = random.randint(19000, 20000)
    oi = random.randint(100000, 500000)
    price = random.randint(19000, 20000)
    
    # VWAP mock
    prices = [price + random.randint(-100, 100) for _ in range(5)]
    volumes = [random.randint(100, 500) for _ in range(5)]
    vwap = round(sum(p * v for p, v in zip(prices, volumes)) / sum(volumes), 2)
    
    return rsi, ema, oi, price, vwap

# ✅ Signal logic
def generate_signal(rsi, ema, price):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    else:
        return "Hold"

# ✅ Loop through all sheets (tabs)
for sheet in all_sheets:
    sheet_name = sheet.title
    print(f"\n📄 Processing Sheet: {sheet_name}")

    try:
        data = sheet.get_all_values()
        header = data[0]
        rows = data[1:]

        for i, row in enumerate(rows):
            symbol = row[0]  # Assuming "Symbol" is in column A
            if not symbol:
                continue

            rsi, ema, oi, price, vwap = get_indicator_values(symbol)
            signal = generate_signal(rsi, ema, price)

            sheet.update_cell(i + 2, 2, price)      # B column = LTP
            sheet.update_cell(i + 2, 3, rsi)        # C column = RSI
            sheet.update_cell(i + 2, 4, ema)        # D column = EMA
            sheet.update_cell(i + 2, 5, oi)         # E column = OI
            sheet.update_cell(i + 2, 6, "N/A")      # F column = Price Action
            sheet.update_cell(i + 2, 7, signal)     # G column = Final Signal
            sheet.update_cell(i + 2, 8, signal)     # H column = Action
            sheet.update_cell(i + 2, 9, vwap)       # I column = VWAP

            print(f"✅ Row {i+2}: {symbol} → {signal} @ {price}")
            send_telegram_message(f"📢 [{sheet_name}] {symbol}: {signal} @ {price} | RSI: {rsi}, EMA: {ema}, OI: {oi}, VWAP: {vwap}")

    except Exception as e:
        print(f"❌ Error in Sheet {sheet_name}: {e}")
