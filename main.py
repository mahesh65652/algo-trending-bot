import os
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from smartapi import SmartConnect

# Load .env variables
load_dotenv()

# Environment variables
api_key = os.getenv("ANGEL_API_KEY")
api_secret = os.getenv("ANGEL_API_SECRET")
client_code = os.getenv("CLIENT_CODE")
totp = os.getenv("TOTP")
sheet_id = os.getenv("SHEET_ID")

# Step 1: Google Sheet Data Fetch
def get_signals():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).sheet1
    data = sheet.get_all_records()

    signals = []
    for row in data:
        if row.get("Action") in ["BUY", "SELL"]:
            signals.append({"symbol": row["Symbol"], "action": row["Action"]})
    return signals

# Step 2: Angel One Login
def angel_login():
    obj = SmartConnect(api_key=api_key)
    data = obj.generateSession(client_code, api_secret, totp)
    return obj

# Step 3: Place Order via Angel One
def place_order(obj, symbol, action):
    print(f"Placing {action} order for {symbol}")
    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": "99926009",  # Replace with real token
            "transactiontype": action,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": "1"
        }
        response = obj.placeOrder(orderparams)
        print("Order Response:", response)
    except Exception as e:
        print("Order Failed:", e)

# Main Flow
if __name__ == "__main__":
    signals = get_signals()
    if signals:
        angel = angel_login()
        for sig in signals:
            place_order(angel, sig['symbol'], sig['action'])
    else:
        print("No Buy/Sell Signals Found.")

