import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import random
import os
import json

print("🚀 Running Algo Trading Bot...")

# ✅ Step 1: Read credentials from correct GitHub secret
creds_dict = json.loads(os.environ['GOOGLE_SHEET_CREDS_JSON'])  # ✅ fixed line
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# ✅ Step 2: Open your target sheet and worksheet
sheet_url = "https://docs.google.com/spreadsheets/d/1-YcTqPTP_mffMWScXv-50wdus_WjWKz1/edit"
sheet = client.open_by_url(sheet_url)
worksheet = sheet.worksheet("NIFTY")

# ✅ Step 3: Read the existing data from Sheet
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# ✅ Step 4: Generate mock indicator values
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

# ✅ Step 6: Loop and update sheet
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

print("✅ Signals updated in Google Sheet.")

