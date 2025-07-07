import os
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi.smartConnect import SmartConnect
import pyotp
import time

# ✅ Google Sheets auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# ✅ Open Google Sheet
sheet_id = os.getenv("SHEET_ID")
sheet_name = os.getenv("SHEET_NAME", "AutoSignal")
sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
data = sheet.get_all_records()
df = pd.DataFrame(data)

# ✅ Angel One credentials
api_key = os.getenv("ANGEL_API_KEY")
api_secret = os.getenv("ANGEL_API_SECRET")
client_code = os.getenv("CLIENT_CODE")
totp_key = os.getenv("TOTP")
totp = pyotp.TOTP(totp_key).now()

# ✅ Angel One Login
smart_api = SmartConnect(api_key)
session = smart_api.generateSession(client_code, totp, api_secret)
if not session.get("access_token"):
    print("❌ Login Failed")
    exit()

print("✅ Logged in successfully. Starting signal generation...")

# ✅ Main Logic Loop
final_signals = []
for i, row in df.iterrows():
    rsi = float(row.get("RSI", 50))
    ema = float(row.get("EMA", 0))
    oi = float(row.get("OI", 0))
    ltp = float(row.get("LTP", 0))

    signal_rsi = "Buy" if rsi < 30 else "Sell" if rsi > 70 else "Hold"
    signal_ema = "Buy" if ltp > ema else "Sell" if ltp < ema else "Hold"
    signal_oi = "Buy" if oi > 0 else "Sell" if oi < 0 else "Hold"

    signals = [signal_rsi, signal_ema, signal_oi]
    if signals.count("Buy") >= 2:
        final = "Buy"
    elif signals.count("Sell") >= 2:
        final = "Sell"
    else:
        final = "Hold"

    final_signals.append(final)
    print(f"{row.get('Symbol')} → Final Signal: {final}")

# ✅ Update sheet with final signal
for idx, sig in enumerate(final_signals):
    sheet.update_cell(idx + 2, df.columns.get_loc("Final Signal") + 1, sig)
    sheet.update_cell(idx + 2, df.columns.get_loc("Action") + 1, sig)

print("✅ All signals updated in Google Sheet.")
