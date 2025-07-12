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

# ✅ Step 1: Google Sheet Auth
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])  # 🔧 Spelling fixed
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# ✅ Step 2: Open your sheet
sheet_url = "https://docs.google.com/spreadsheets/d/1-YcTqPTP_mffMWScXv-50wdus_WjWKz1/edit"
sheet = client.open_by_url(sheet_url)
worksheet = sheet.worksheet("NIFTY")

# ✅ Step 3: Read Sheet Data
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# ✅ Step 4: Mock Indicator Logic
def get_indicator_values(symbol):
    rsi = random.randint(10, 90)
    ema = random.randint(19000, 20000)
    oi = random.randint(100000, 500000)
    price = random.randint(19000, 20000)
    return rsi, ema, oi, price

# ✅ Step 5: Generate Signal
def generate_signal(rsi, ema, price):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    else:
        return "Hold"

# ✅ Step 6: Loop and update Google Sheet
for i, row in df.iterrows():
    symbol = row["Symbol"]
    rsi, ema, oi, price = get_indicator_values(symbol)
    signal = generate_signal(rsi, ema, price)

    worksheet.update_cell(i + 2, 2, price)      # LTP
    worksheet.update_cell(i + 2, 3, rsi)        # RSI
    worksheet.update_cell(i + 2, 4, ema)        # EMA
    worksheet.update_cell(i + 2, 5, oi)         # OI
    worksheet.update_cell(i + 2, 6, "N/A")      # Price Action
    worksheet.update_cell(i + 2, 7, signal)     # Final Signal
    worksheet.update_cell(i + 2, 8, signal)     # Action

# ✅ Final Confirmation
print("✅ Signals updated in Google Sheet.")
send_telegram_message("✅ Signals updated successfully in Google Sheet.")
