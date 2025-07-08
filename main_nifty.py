import os
import time
import pyotp
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from SmartApi.smartConnect import SmartConnect

# ✅ Google Sheet Auth
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials_nifty.json", scopes=scope)
client = gspread.authorize(creds)

# ✅ NIFTY Sheet
sheet_id = os.getenv("NIFTY_SHEET_ID")
sheet_name = os.getenv("NIFTY_SHEET_NAME", "AutoSignal")
sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
data = sheet.get_all_records()
df = pd.DataFrame(data)

# ✅ Angel One credentials
api_key = os.getenv("ANGEL_API_KEY")
api_secret = os.getenv("ANGEL_API_SECRET")
client_code = os.getenv("CLIENT_CODE")
totp_key = os.getenv("TOTP")
totp = pyotp.TOTP(totp_key).now()

smart_api = SmartConnect(api_key)
session = smart_api.generateSession(client_code, totp, api_secret)
if not session.get("access_token"):
    print("❌ Login Failed")
    exit()

print("✅ Logged in for NIFTY")

# ✅ Signal Logic
final_signals = []
for i, row in df.iterrows():
    try:
        rsi = float(row.get("RSI", 50))
        ema = float(row.get("EMA", 0))
        oi = float(row.get("OI", 0))
        ltp = float(row.get("LTP", 0))

        signal_rsi = "Buy" if rsi < 30 else "Sell" if rsi > 70 else "Hold"
        signal_ema = "Buy" if ltp > ema else "Sell" if ltp < ema else "Hold"
        signal_oi = "Buy" if oi > 0 else "Sell" if oi < 0 else "Hold"

        signals = [signal_rsi, signal_ema, signal_oi]
        final = "Buy" if signals.count("Buy") >= 2 else "Sell" if signals.count("Sell") >= 2 else "Hold"
        final_signals.append(final)

        print(f"NIFTY → {row.get('Symbol')} → Final Signal: {final}")
    except Exception as e:
        print(f"⚠️ Error in row {i+2}: {e}")
        final_signals.append("Hold")

# ✅ Update Sheet
for idx, sig in enumerate(final_signals):
    sheet.update_cell(idx + 2, df.columns.get_loc("Final Signal") + 1, sig)
    sheet.update_cell(idx + 2, df.columns.get_loc("Action") + 1, sig)

print("✅ NIFTY Signals updated")

