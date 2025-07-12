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
sheet_name = os.environ.get("SHEET_NAME", "AutoSignal")
sheet = client.open_by_key(sheet_id).worksheet(sheet_name)

# ✅ Read Data
data = sheet.get_all_records()
df = pd.DataFrame(data)

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

# ✅ Loop through each row
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

    send_telegram_message(f"📢 {symbol}: {signal} @ {price} | RSI: {rsi}, EMA: {ema}, OI: {oi}")

print("✅ Sheet updated and alerts sent.")
