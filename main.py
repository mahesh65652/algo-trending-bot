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

import gspread
import pandas as pd
from smartapi import SmartConnect
from datetime import datetime
import time

# ✅ ANGEL ONE API KE DETAILS
api_key = "अपना_API_KEY"
client_id = "अपना_CLIENT_ID"
client_secret = "अपना_CLIENT_SECRET"
jwt_token = "अपना_JWT_TOKEN"
feed_token = "अपना_FEED_TOKEN"

# ✅ GOOGLE SHEET AUTH
gc = gspread.service_account(filename="creds.json")

# ✅ Sheet और Tabs के नाम
sheet = gc.open("Algo Trading Sheet")
tabs = ["BANKNIFTY", "NIFTY50", "FINNIFTY", "CRUDEOIL", "SILVER", "GOLD", "NG"]

# ✅ Angel API Auth
obj = SmartConnect(api_key=api_key)
obj.generateSession(client_id, client_secret)
feedToken = feed_token

# ✅ Symbol और Token Mapping
symbol_token_map = {
    "BANKNIFTY": "99926009",
    "NIFTY50": "99926000",
    "FINNIFTY": "99926037",
    "CRUDEOIL": "17013",
    "SILVER": "17104",
    "GOLD": "17100",
    "NG": "17011",
}

# ✅ Indicator Calculation
def calculate_indicators(data):
    data["EMA"] = data["LTP"].ewm(span=10).mean()
    data["RSI"] = 100 - (100 / (1 + data["LTP"].pct_change().rolling(14).mean()))
    return data

# ✅ MAIN LOOP
for tab in tabs:
    worksheet = sheet.worksheet(tab)
    data = worksheet.get_all_records()

    if not data:
        continue

    df = pd.DataFrame(data)
    ltps = []

    for index, row in df.iterrows():
        symbol = row["Symbol"]
        token = symbol_token_map.get(symbol.upper(), None)
        if token is None:
            ltps.append("")
            continue

        try:
            ltp_data = obj.ltpData("NSE", symbol.upper(), token)
            ltp = float(ltp_data["data"]["ltp"])
            ltps.append(ltp)
        except:
            ltps.append("")

    df["LTP"] = ltps
    df = calculate_indicators(df)

    # ✅ Final Signal Logic (Example: RSI > 60 = BUY, < 40 = SELL)
    df["Final Signal"] = df.apply(lambda row: "BUY" if row["RSI"] > 60 else ("SELL" if row["RSI"] < 40 else "HOLD"), axis=1)

    # ✅ Update Google Sheet
    updated_data = df.values.tolist()
    worksheet.update("A2", updated_data)

    print(f"{tab} ✅ Updated")

print("🎯 FINAL RUN COMPLETE")

