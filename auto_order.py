import os
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from SmartApi.smartConnect import SmartConnect
import pyotp

def main():
    # 🔐 Load Environment Variables
    SHEET_ID = os.getenv("SHEET_ID")
    SHEET_NAME = os.getenv("SHEET_NAME", "AutoSignal")
    api_key = os.getenv("ANGEL_API_KEY")
    api_secret = os.getenv("ANGEL_API_SECRET")
    client_code = os.getenv("CLIENT_CODE")
    totp_key = os.getenv("TOTP")

    if not all([SHEET_ID, api_key, api_secret, client_code, totp_key]):
        print("❌ One or more environment variables missing")
        return

    # ✅ Google Sheets Auth
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)

    try:
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    except Exception as e:
        print(f"❌ Sheet Load Error: {e}")
        return

    df = pd.DataFrame(sheet.get_all_records())

    # ✅ Angel One Login
    totp = pyotp.TOTP(totp_key).now()
    smart_api = SmartConnect(api_key)
    session = smart_api.generateSession(client_code, totp, api_secret)

    if not session.get("access_token"):
        print(f"❌ Angel Login Failed: {session}")
        return
    print("✅ Angel One Logged In")

    # 🔁 Order Placement
    for idx, row in df.iterrows():
        symbol = row.get("Symbol")
        token = str(row.get("Token"))
        signal = row.get("Final Signal", "").upper()
        quantity = int(row.get("Qty", 1))

        if signal not in ("BUY", "SELL"):
            continue

        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": signal,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": quantity
        }

        try:
            order_id = smart_api.placeOrder(order_params)
            print(f"✅ Order: {symbol} | {signal} | ID={order_id}")

            if "Action" in df.columns:
                sheet.update_cell(idx + 2, df.columns.get_loc("Action") + 1, signal)
        except Exception as e:
            print(f"❌ Error: {symbol} | {e}")

if __name__ == "__main__":
    main()
import os, json, gspread, time
from SmartApi.smartConnect import SmartConnect
from oauth2client.service_account import ServiceAccountCredentials

# Angel One Auth
client = SmartConnect(api_key=os.environ['API_KEY'])
access_token = os.environ['ACCESS_TOKEN']
client.set_access_token(access_token)

# Google Sheet Auth
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client_gs = gspread.authorize(creds)

# Open Sheet
sheet_id = os.environ['SHEET_ID']
sheet = client_gs.open_by_key(sheet_id).sheet1  # Main sheet
rows = sheet.get_all_values()[1:]  # skip header

# Loop & Place Orders
for i, row in enumerate(rows):
    symbol = row[0].strip()
    signal = row[7].strip()  # H = Action
    ltp = float(row[1]) if row[1] else 0  # B = LTP

    if signal not in ["Buy", "Sell"]:
        continue

    try:
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": "26000",  # Placeholder, आपको सही token चाहिए
            "transactiontype": signal.upper(),
            "exchange": "MCX",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": 0,
            "quantity": 1
        }

        order_id = client.placeOrder(order_params)
        print(f"✅ Order Placed: {symbol} {signal} → {order_id}")
        sheet.update_cell(i+2, 10, "✔️")  # J = Status

    except Exception as e:
        print(f"❌ Order Failed for {symbol}: {e}")
        sheet.update_cell(i+2, 10, "❌")  # J = Status

import os, json, time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from smartapi import SmartConnect
import requests

# ✅ Telegram Alert (Optional)
def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": message})

# ✅ Token Mapping (MCX + NSE)
token_map = {
    "CRUDEOIL": {"token": "21906", "exchange": "MCX"},
    "NATURALGAS": {"token": "21921", "exchange": "MCX"},
    "SILVER": {"token": "22032", "exchange": "MCX"},
    "GOLD": {"token": "21837", "exchange": "MCX"},
    "NIFTY": {"token": "3045", "exchange": "NSE"},
    "BANKNIFTY": {"token": "26009", "exchange": "NSE"},
    "RELIANCE": {"token": "2885", "exchange": "NSE"},
    "TCS": {"token": "11536", "exchange": "NSE"}
    # Add more symbols here
}

# ✅ Angel One Login
client_id = os.environ['CLIENT_ID']
api_key = os.environ['API_KEY']
refresh_token = os.environ['FEED_TOKEN']

obj = SmartConnect(api_key=api_key)
session = obj.generateSession(client_id, refresh_token)
auth_token = session['data']['jwtToken']

# ✅ Google Sheet Auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet_id = os.environ['SHEET_ID']
spreadsheet = client.open_by_key(sheet_id)
sheets = spreadsheet.worksheets()

# ✅ Order Function
def place_order(symbol, action):
    if symbol not in token_map:
        print(f"❌ Symbol Not Found: {symbol}")
        return "❌ Symbol Not Found"

    token_info = token_map[symbol]
    orderparams = {
        "variety": "NORMAL",
        "tradingsymbol": symbol,
        "symboltoken": token_info["token"],
        "transactiontype": action.upper(),
        "exchange": token_info["exchange"],
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "price": 0,
        "quantity": 1
    }

    try:
        orderId = obj.placeOrder(orderparams)
        print(f"✅ Order Placed: {symbol} → {action} → ID: {orderId}")
        return f"✅ Order ID: {orderId}"
    except Exception as e:
        print(f"❌ Order Failed: {symbol} → {action} → {e}")
        return f"❌ {e}"

# ✅ Process All Sheets
for sheet in sheets:
    print(f"\n📄 Sheet: {sheet.title}")
    data = sheet.get_all_values()
    rows = data[1:]

    for i, row in enumerate(rows):
        symbol = row[0].strip().upper()
        action = row[7].strip().capitalize()  # Column H
        status = row[8].strip() if len(row) > 8 else ""

        if action in ["Buy", "Sell"] and status != "Order Placed":
            result = place_order(symbol, action)
            sheet.update_cell(i + 2, 9, "Order Placed")  # Column I
            send_telegram(f"📢 {symbol} → {action} → {result}")
            time.sleep(1)

print("✅ All Orders Processed.")

import os
import json
import time
import gspread
import requests
from smartapi import SmartConnect
from oauth2client.service_account import ServiceAccountCredentials

# ✅ Telegram Alert (Optional)
def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": message})

# ✅ Token Mapping (Customize as per your sheet)
token_map = {
    "CRUDEOIL": {"token": "21906", "exchange": "MCX"},
    "NATURALGAS": {"token": "21921", "exchange": "MCX"},
    "SILVER": {"token": "22032", "exchange": "MCX"},
    "GOLD": {"token": "21837", "exchange": "MCX"},
    "NIFTY": {"token": "3045", "exchange": "NSE"},
    "BANKNIFTY": {"token": "26009", "exchange": "NSE"},
    "RELIANCE": {"token": "2885", "exchange": "NSE"},
    "TCS": {"token": "11536", "exchange": "NSE"}
}

# ✅ Angel One Login
client_id = os.environ['CLIENT_ID']
api_key = os.environ['API_KEY']
refresh_token = os.environ['FEED_TOKEN']

obj = SmartConnect(api_key=api_key)
session = obj.generateSession(client_id, refresh_token)
auth_token = session['data']['jwtToken']

# ✅ Google Sheet Auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet_id = os.environ['SHEET_ID']
spreadsheet = client.open_by_key(sheet_id)
sheets = spreadsheet.worksheets()

# ✅ Place Order Function
def place_order(symbol, action):
    if symbol not in token_map:
        return f"❌ Symbol not in map: {symbol}"

    token_info = token_map[symbol]
    order_params = {
        "variety": "NORMAL",
        "tradingsymbol": symbol,
        "symboltoken": token_info["token"],
        "transactiontype": action.upper(),
        "exchange": token_info["exchange"],
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "price": 0,
        "quantity": 1
    }

    try:
        order_id = obj.placeOrder(order_params)
        print(f"✅ Order Placed: {symbol} | {action} | ID: {order_id}")
        return f"✅ Order ID: {order_id}"
    except Exception as e:
        print(f"❌ Order Failed: {symbol} | {action} | Error: {e}")
        return f"❌ {e}"

# ✅ Loop through all sheets and process signals
for sheet in sheets:
    print(f"\n📄 Processing Sheet: {sheet.title}")
    data = sheet.get_all_values()
    rows = data[1:]  # skip header

    for i, row in enumerate(rows):
        try:
            symbol = row[0].strip().upper()
            action = row[7].strip().capitalize()  # Column H = Action
            status = row[8].strip() if len(row) > 8 else ""  # Column I = Status

            if action in ["Buy", "Sell"] and status != "Order Placed":
                result = place_order(symbol, action)
                sheet.update_cell(i + 2, 9, "Order Placed")  # Column I
                send_telegram(f"📢 {symbol} → {action} → {result}")
                time.sleep(1)
        except Exception as e:
            print(f"⚠️ Row Error: {i+2} → {e}")

print("✅ All Orders Processed.")

import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi import SmartConnect
import pyotp
import requests

# ENV Variables
SHEET_ID = os.getenv("SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")
API_KEY = os.getenv("ANGEL_API_KEY")
API_SECRET = os.getenv("ANGEL_API_SECRET")
CLIENT_CODE = os.getenv("CLIENT_CODE")
TOTP_KEY = os.getenv("TOTP")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Step 1: Telegram Alert Function
def send_telegram(msg):
    if msg:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=data)

# Step 2: Angel One Login
def angel_login():
    smartApi = SmartConnect(api_key=API_KEY)
    token = pyotp.TOTP(TOTP_KEY).now()
    data = smartApi.generateSession(CLIENT_CODE, API_SECRET, token)
    return smartApi, data["data"]["refreshToken"]

# Step 3: Read Google Sheet
def read_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(eval(os.getenv("GOOGLE_CREDENTIALS_JSON")), scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    return sheet.get_all_records()

# Step 4: Place Orders from Sheet Signals
def place_orders():
    smartApi, refresh_token = angel_login()
    rows = read_sheet()
    for row in rows:
        action = row.get("Action", "").strip().upper()
        symbol = row.get("Symbol", "").strip()
        qty = int(row.get("Qty", 0))
        exch = "NSE"
        tradingsymbol = symbol
        if action in ["BUY", "SELL"] and qty > 0:
            order_type = "BUY" if action == "BUY" else "SELL"
            try:
                orderparams = {
                    "variety": "NORMAL",
                    "tradingsymbol": tradingsymbol,
                    "symboltoken": "99926000",  # update with correct token
                    "transactiontype": order_type,
                    "exchange": exch,
                    "ordertype": "MARKET",
                    "producttype": "INTRADAY",
                    "duration": "DAY",
                    "price": 0,
                    "squareoff": "0",
                    "stoploss": "0",
                    "quantity": qty
                }
                orderId = smartApi.placeOrder(orderparams)
                send_telegram(f"{order_type} Order Placed: {symbol}, Qty: {qty}, ID: {orderId}")
            except Exception as e:
                send_telegram(f"❌ Failed to place {order_type} order for {symbol}: {str(e)}")

place_orders()
