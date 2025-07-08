# auto_order.py

import os
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from SmartApi.smartConnect import SmartConnect
import pyotp

def main():
    # 📌 Google Sheets Authentication
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)

    # 📌 Google Sheet Setup
    SHEET_ID = os.getenv("SHEET_ID")
    SHEET_NAME = os.getenv("SHEET_NAME", "AutoSignal")
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

    # 📌 Read data into DataFrame
    df = pd.DataFrame(sheet.get_all_records())

    # 📌 Angel One Authentication
    api_key = os.getenv("ANGEL_API_KEY")
    api_secret = os.getenv("ANGEL_API_SECRET")
    client_code = os.getenv("CLIENT_CODE")           # Your Angel One client code
    totp_key = os.getenv("TOTP")                     # Your TOTP secret
    totp = pyotp.TOTP(totp_key).now()

    smart_api = SmartConnect(api_key)
    session = smart_api.generateSession(client_code, totp, api_secret)
    if not session.get("access_token"):
        print("❌ Angel One Login Failed")
        return
    print("✅ Angel One Logged In")

    # 📌 Place orders based on Final Signal
    for idx, row in df.iterrows():
        symbol = row.get("Symbol")
        token = str(row.get("Token"))
        signal = row.get("Final Signal", "").upper()

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
            "quantity": "1"
        }

        try:
            order_id = smart_api.placeOrder(order_params)
            print(f"✅ Order placed: {symbol} | {signal} | ID={order_id}")
            sheet.update_cell(idx + 2, df.columns.get_loc("Action") + 1, signal)
        except Exception as e:
            print(f"❌ Error placing order for {symbol}: {e}")

if __name__ == "__main__":
    main()

