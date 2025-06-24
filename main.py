import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi.smartConnect import SmartConnect
import pyotp

# ✅ Save credentials.json file from GitHub Secrets (already done in GitHub Actions step)

# ✅ Authenticate Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

sheet_id = os.getenv("SHEET_ID")
sheet = client.open_by_key(sheet_id).sheet1
data = sheet.get_all_records()

# ✅ Angel One SmartAPI credentials from GitHub Secrets
api_key = os.getenv("ANGEL_API_KEY")
api_secret = os.getenv("ANGEL_API_SECRET")
client_code = os.getenv("CLIENT_CODE")
totp_key = os.getenv("TOTP")  # TOTP secret key for 2FA

# ✅ Generate TOTP
totp = pyotp.TOTP(totp_key).now()

# ✅ Initialize SmartConnect
smart_api = SmartConnect(api_key)
session = smart_api.generateSession(client_code, totp, api_secret)

# ✅ Place order for each signal
for row in data:
    symbol = row['Symbol']
    signal = row['Final Signal'].strip().upper()

    if signal in ["BUY", "SELL"]:
        print(f"🔁 Processing {symbol} for signal: {signal}")

        try:
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": "99926009",  # ❗Update this dynamically later
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
            print(f"✅ Order Placed for {symbol} | ID: {order_id}")

        except Exception as e:
            print(f"❌ Failed to place order for {symbol}: {e}")
