import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi.smartConnect import SmartConnect
import pyotp

# ✅ Google Sheets auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# ✅ Open Google Sheet
sheet_id = os.getenv("SHEET_ID")
sheet_name = os.getenv("SHEET_NAME") or "AutoSignal"
sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
data = sheet.get_all_records()

# ✅ Angel One credentials
api_key = os.getenv("ANGEL_API_KEY")
api_secret = os.getenv("ANGEL_API_SECRET")
client_code = os.getenv("CLIENT_CODE")
totp_key = os.getenv("TOTP")

# ✅ TOTP for login
totp = pyotp.TOTP(totp_key).now()

# ✅ Angel One Login
smart_api = SmartConnect(api_key)
session = smart_api.generateSession(client_code, totp, api_secret)

if not session.get("access_token"):
    print("❌ Login Failed. Check credentials or TOTP.")
    exit()

# ✅ Fetch token map (symbol → token)
token_map = {}
instruments = smart_api.getProfile()["data"].get("exchanges")  # You can load NSE instrument list from file too

# (Optional: you can replace this with a static dict or a file for faster lookup)
# Example: token_map = {"RELIANCE-EQ": "99926009"}

# ✅ Place order loop
for row in data:
    symbol = row.get("Symbol")
    signal = row.get("Final Signal", "").strip().upper()

    if signal not in ["BUY", "SELL"]:
        continue

    try:
        # You should have a pre-saved token map for production use
        symbol_token = row.get("Token") or "99926009"  # fallback
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": symbol_token,
            "transactiontype": signal,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": "1"
        }

        order_id = smart_api.placeOrder(order_params)
        print(f"✅ Order Placed: {symbol} | Signal: {signal} | ID: {order_id}")

    except Exception as e:
        print(f"❌ Error placing order for {symbol}: {e}")
