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

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from smartapi import SmartConnect
import time

# ====== CONFIGURATION ======
GOOGLE_SHEET_NAME = "Your Sheet Name Here"
TABS = ["BANKNIFTY", "NIFTY50", "FINNIFTY", "CRUDOIL", "SILVER", "GOLD", "NG"]
ROW_INDEX = 2  # A2 row
EMAIL_COLUMN = "A"

# Angel One Credentials
api_key = "YOUR_API_KEY"
client_id = "YOUR_CLIENT_ID"
pwd = "YOUR_PASSWORD"
totp = "YOUR_TOTP"

# ====== AUTHENTICATION ======

# Authenticate Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME)

# Authenticate Angel One API
obj = SmartConnect(api_key)
data = obj.generateSession(client_id, pwd, totp)
auth_token = data['data']['jwtToken']
refresh_token = data['data']['refreshToken']
feed_token = obj.getfeedToken()

# ====== LOGIC ======

def place_order(symbol, action):
    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": "XYZTOKEN",  # You need to fetch real token for this symbol
            "transactiontype": action,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": 1
        }
        orderId = obj.placeOrder(orderparams)
        print(f"Order placed: {symbol} - {action} - Order ID: {orderId}")
        return f"Order ID: {orderId}"
    except Exception as e:
        return f"Error: {e}"

def process_tab(tab_name):
    ws = sheet.worksheet(tab_name)
    values = ws.row_values(ROW_INDEX)

    try:
        symbol = values[0]
        ltp = float(values[1])
        rsi = float(values[2])
        ema = float(values[3])
        oi = float(values[4])
        price_action = values[5]

        # ---- SIGNAL LOGIC ----
        final_signal = "HOLD"
        if rsi > 60 and ltp > ema and "Bullish" in price_action:
            final_signal = "BUY"
        elif rsi < 40 and ltp < ema and "Bearish" in price_action:
            final_signal = "SELL"

        # Update final signal in sheet
        ws.update_acell(f"G{ROW_INDEX}", final_signal)

        # Place order if BUY/SELL
        if final_signal in ["BUY", "SELL"]:
            result = place_order(symbol, final_signal)
            ws.update_acell(f"H{ROW_INDEX}", final_signal)
            ws.update_acell(f"N{ROW_INDEX}", result)
        else:
            ws.update_acell(f"H{ROW_INDEX}", "HOLD")

    except Exception as e:
        print(f"Error in tab {tab_name}: {e}")
        ws.update_acell(f"N{ROW_INDEX}", f"Error: {e}")

# ====== MAIN ======
for tab in TABS:
    process_tab(tab)
    time.sleep(1)

print("✅ All tabs processed.")
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from smartapi import SmartConnect
import time

# === CONFIGURATION ===
sheet_names = ['BANKNIFTY', 'NIFTY50', 'FINNIFTY', 'CRUDEOIL', 'GOLD', 'SILVER', 'NG']
quantity = 1

# === GOOGLE SHEET SETUP ===
scope = ["https://spreadsheets.google.com/feeds",
         'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# 🔁 YOUR GOOGLE SHEET URL HERE
spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1zNq9Hq9QaNwE7my9xGkq28hI9UNuYai4YV3P9hUzWxQ/edit")

# === ANGEL ONE API SETUP ===
api_key = "xxxxxxxxxxx"
client_id = "xxxxxxxxxxx"
pin = "xxxx"
totp = "xxxxxx"

smartApi = SmartConnect(api_key=api_key)
login_data = smartApi.generateSession(client_id, pin, totp)

# 🔄 GET SYMBOLTOKEN FROM ANGEL API OR STATIC MAPPING
symbol_tokens = {
    "BANKNIFTY": "99926009",
    "NIFTY50": "99926000",
    "FINNIFTY": "99926004",
    "CRUDEOIL": "26009",
    "GOLD": "26018",
    "SILVER": "26019",
    "NG": "26003"
}

def place_order(symbol, action, price, token):
    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": action.upper(),
            "exchange": "NSE" if symbol in ['BANKNIFTY', 'NIFTY50', 'FINNIFTY'] else "MCX",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "quantity": quantity
        }
        response = smartApi.placeOrder(orderparams)
        print("✅ Order Placed:", response)
        return "✅ Done"
    except Exception as e:
        print("❌ Error placing order:", e)
        return "❌ Error"

# === LOOP THROUGH EACH SHEET TAB ===
for sheet_name in sheet_names:
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        records = sheet.get_all_records()

        for i, row in enumerate(records, start=2):
            symbol = row.get("Symbol")
            action = row.get("Action", "").strip().lower()
            ltp = row.get("LTP", 0)

            if symbol and action in ["buy", "sell"]:
                token = symbol_tokens.get(sheet_name, "")
                if not token:
                    print(f"⚠️ No token found for {symbol}")
                    continue
                print(f"📢 {action.upper()} => {symbol} @ {ltp}")
                result = place_order(symbol, action, ltp, token)
                sheet.update_cell(i, 14, result)

    except Exception as e:
        print(f"⚠️ Error in sheet '{sheet_name}':", e)

import gspread
import os, json, requests, time
import pandas as pd
from smartapi import SmartConnect
from oauth2client.service_account import ServiceAccountCredentials

# ✅ Telegram
def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat_id, "text": msg})

# ✅ Angel One Login
api_key = os.environ["ANGEL_API_KEY"]
client_id = os.environ["ANGEL_CLIENT_ID"]
pwd = os.environ["ANGEL_PASSWORD"]
totp = os.environ["ANGEL_TOTP"]

smartApi = SmartConnect(api_key)
session = smartApi.generateSession(client_id, pwd, totp)
feed_token = smartApi.getfeedToken()

# ✅ Token mapping
symbol_tokens = {
    "BANKNIFTY": "99926009",
    "NIFTY50": "99926000",
    "FINNIFTY": "99926004",
    "CRUDEOIL": "26009",
    "GOLD": "26018",
    "SILVER": "26019",
    "NG": "26003"
}

# ✅ Google Sheet Setup
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)

spreadsheet = gc.open_by_key(os.environ["SHEET_ID"])
sheet_names = ["BANKNIFTY", "NIFTY50", "FINNIFTY", "CRUDEOIL", "GOLD", "SILVER", "NG"]

# ✅ Place Order
def place_order(symbol, action, token):
    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": action.upper(),
            "exchange": "NSE" if symbol in ["BANKNIFTY", "NIFTY50", "FINNIFTY"] else "MCX",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "quantity": 1
        }
        result = smartApi.placeOrder(orderparams)
        return f"✅ Order Placed: {result}"
    except Exception as e:
        return f"❌ Order Error: {e}"

# ✅ Loop Each Sheet
for sheet_name in sheet_names:
    ws = spreadsheet.worksheet(sheet_name)
    data = ws.get_all_records()

    for i, row in enumerate(data, start=2):
        try:
            symbol = row.get("Symbol", "").strip().upper()
            action = row.get("Action", "").strip().upper()

            if symbol and action in ["BUY", "SELL"]:
                token = symbol_tokens.get(sheet_name)
                result = place_order(symbol, action, token)
                ws.update_cell(i, 14, result)
                send_telegram(f"{sheet_name}: {symbol} → {action}\n{result}")
            else:
                ws.update_cell(i, 14, "HOLD")

        except Exception as e:
            ws.update_cell(i, 14, f"⚠️ Error: {e}")
            send_telegram(f"❌ Error in {sheet_name}: {e}")

print("✅ All tabs processed successfully.")

import os
import gspread
import pandas as pd
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# ========== 🔐 Environment Variables ==========
GOOGLE_SHEET_ID_NSE = os.getenv("SHEET_ID")
GOOGLE_SHEET_ID_MCX = os.getenv("MCX_SHEET_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ========== 🌐 Google Sheet Auth ==========
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
client = gspread.authorize(credentials)

# ========== 📤 Telegram Alert ==========
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': msg}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram Error:", e)

# ========== 📈 Indicator Logic ==========
def get_signal(rsi, price, ema, oi, price_action):
    if rsi and ema and oi:
        if rsi < 30 and price > ema and "BUY" in price_action:
            return "BUY"
        elif rsi > 70 and price < ema and "SELL" in price_action:
            return "SELL"
    return "HOLD"

# ========== 🔁 Process Each Sheet ==========
def process_sheet(sheet_id, market_type):
    sheet = client.open_by_key(sheet_id).sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    final_signals = []
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

    for i, row in df.iterrows():
        symbol = row.get("Symbol")
        price = float(row.get("LTP", 0))
        rsi = float(row.get("RSI", 0))
        ema = float(row.get("EMA", 0))
        oi = float(row.get("OI", 0))
        price_action = row.get("Price Action", "").upper()

        signal = get_signal(rsi, price, ema, oi, price_action)
        final_signals.append(signal)

        # 🧾 Log or Alert
        if signal in ["BUY", "SELL"]:
            send_telegram(f"📢 {market_type} | {symbol} | {signal}\n💰Price: {price} | RSI: {rsi} | EMA: {ema} | OI: {oi}\n🕒 {now}")

    # Update Final Signal Column
    try:
        col_index = df.columns.get_loc("Final Signal") + 1
        sheet.batch_update([{
            'range': f"{chr(65 + col_index)}2:{chr(65 + col_index)}{len(df)+1}",
            'values': [[s] for s in final_signals]
        }])
        print(f"✅ {market_type} Signals Updated")
    except Exception as e:
        print("❌ Error Updating Sheet:", e)

# ========== 🚀 Main ==========
if __name__ == "__main__":
    print("🚀 Running Algo Bot")
    process_sheet(GOOGLE_SHEET_ID_NSE, "NSE")
    process_sheet(GOOGLE_SHEET_ID_MCX, "MCX")
    print("✅ Done")
