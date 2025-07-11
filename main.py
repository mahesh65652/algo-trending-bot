import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import random  # Replace with real data fetching in future

print("🚀 Running Algo Trading Bot...")

# Step 1: Google Sheet Authentication
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Step 2: Open your target sheet and worksheet
sheet_url = "https://docs.google.com/spreadsheets/d/1-YcTqPTP_mffMWScXv-50wdus_WjWKz1/edit"
sheet = client.open_by_url(sheet_url)
worksheet = sheet.worksheet("NIFTY")

# Step 3: Read the existing data from Sheet
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Step 4: Function to generate mock indicator values
def get_indicator_values(symbol):
    rsi = random.randint(10, 90)
    ema = random.randint(19000, 20000)
    oi = random.randint(100000, 500000)
    price = random.randint(19000, 20000)
    return rsi, ema, oi, price

# Step 5: Generate Signal based on logic
def generate_signal(rsi, ema, price):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    else:
        return "Hold"

# Step 6: Loop through rows and update indicators + signal
for i, row in df.iterrows():
    symbol = row["Symbol"]
    rsi, ema, oi, price = get_indicator_values(symbol)
    signal = generate_signal(rsi, ema, price)

    # Update the sheet columns accordingly
    worksheet.update_cell(i + 2, 2, price)      # LTP
    worksheet.update_cell(i + 2, 3, rsi)        # RSI
    worksheet.update_cell(i + 2, 4, ema)        # EMA
    worksheet.update_cell(i + 2, 5, oi)         # OI
    worksheet.update_cell(i + 2, 6, "N/A")      # Price Action (optional)
    worksheet.update_cell(i + 2, 7, signal)     # Final Signal
    worksheet.update_cell(i + 2, 8, signal)     # Action

print("✅ Signals updated in Google Sheet.")
