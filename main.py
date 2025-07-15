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


print("\n✅ All Sheets processed successfully.")
import gspread
from datetime import datetime

# ✅ Step 1: Service Account JSON Credentials
SERVICE_ACCOUNT_FILE = 'credentials.json'  # इस नाम से JSON फाइल सेव करें

# ✅ Step 2: आपकी Google Sheet की ID
SHEET_ID = '1xJQI1vYxPZKmX2tdsCpkMUaY2Hq08Z1ZhiEHpJEx0Dk'
SHEET_TAB = 'BankNifty'  # आपकी Sheet का नाम (जैसा कि Sheet में है)

# ✅ Step 3: Google Sheet से कनेक्ट करें
try:
    client = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(SHEET_TAB)
    print(f"✅ Sheet '{SHEET_TAB}' से सफलतापूर्वक कनेक्ट हो गया।")
except Exception as e:
    print(f"❌ Sheet को खोलने में Error: {e}")
    exit()

# ✅ Step 4: Sheet से डेटा पढ़ें
try:
    data = worksheet.get_all_values()
    print(f"📊 कुल पंक्तियाँ: {len(data)}")
except Exception as e:
    print(f"❌ डेटा पढ़ने में Error: {e}")
    exit()

# ✅ Step 5: Sheet में एक मैसेज वापस लिखें
try:
    now = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    message = f"✅ Accessed at {now}"
    
    # Sheet की पहली पंक्ति, Column 10 (J कॉलम) में मैसेज लिखें
    worksheet.update_cell(1, 10, message)
    print(f"🟢 Cell अपडेट हुआ: '{message}'")
except Exception as e:
    print(f"❌ Sheet में लिखने में Error: {e}")
