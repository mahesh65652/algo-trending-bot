import os
import json
import gspread
import pandas as pd
from SmartApi.smartConnect import SmartConnect
from datetime import datetime

# -------------------------
# Google Sheets Auth
# -------------------------
creds_dict = json.loads(os.environ['GSHEET_CREDS_JSON'])
gc = gspread.service_account_from_dict(creds_dict)
sheet = gc.open_by_key(os.environ['GSHEET_ID']).sheet1

# -------------------------
# Angel One Auth
# -------------------------
API_KEY = os.environ['ANGEL_API_KEY']
API_SECRET = os.environ['ANGEL_API_SECRET']
CLIENT_CODE = os.environ['CLIENT_CODE']
TOTP = os.environ['TOTP']

smart = SmartConnect(api_key=API_KEY)
data = smart.generateSession(CLIENT_CODE, API_SECRET, TOTP)
auth_token = data['data']['jwtToken']

# -------------------------
# Token Map (NSE Index only)
# -------------------------
token_map = {
    "NIFTY": "99926000",        # Nifty 50
    "BANKNIFTY": "99926007",    # Nifty Bank
    "FINNIFTY": "99926037",     # Nifty Financial Services
    "MIDCPNIFTY": "99926062",   # Nifty Midcap Select
    "SENSEX": "1"               # BSE Sensex
}

# -------------------------
# Fetch LTP Data
# -------------------------
rows = []
for name, token in token_map.items():
    try:
        ltp_data = smart.ltpData('NSE', name, token)
        ltp = ltp_data['data']['ltp']
        rows.append([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, ltp])
    except Exception as e:
        rows.append([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, f"Error: {e}"])

# -------------------------
# Update Google Sheet
# -------------------------
df = pd.DataFrame(rows, columns=["Timestamp", "Symbol", "LTP"])
sheet.clear()
sheet.update([df.columns.values.tolist()] + df.values.tolist())

print("✅ Sheet updated successfully!")
