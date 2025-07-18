import json
import time
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi.smartConnect import SmartConnect
from datetime import datetime

# Load credentials
with open("credentials.json") as f:
    creds = json.load(f)

api_key = creds["api_key"]
client_id = creds["client_id"]
password = creds["password"]
totp = creds["totp"]

# Angel One login
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(client_id, password, totp)
feed_token = obj.getfeedToken()
refresh_token = data['data']['refreshToken']

# Google Sheets Auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("gspread-credentials.json", scope)
client = gspread.authorize(credentials)

sheet = client.open_by_url("<YOUR GOOGLE SHEET URL>").sheet1

# Read Sheet into DataFrame
data = sheet.get_all_records()
df = pd.DataFrame(data)

# Process each row
for index, row in df.iterrows():
    symbol = row['Symbol']
    segment = row['Segment'].upper()

    try:
        ltp_data = obj.ltpData(exchange=segment, tradingsymbol=symbol, symboltoken="")
        ltp = float(ltp_data['data']['ltp'])
        
        # Dummy logic for indicators
        rsi = round((ltp % 70) + 20, 2)  # just mock RSI
        ema = round(ltp * 0.98, 2)       # mock EMA
        oi = round(ltp * 1.5, 2)         # mock OI

        # Price Action and Final Signal
        if ltp > ema and rsi > 60:
            signal = "BUY"
        elif ltp < ema and rsi < 40:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Update back to sheet
        sheet.update_cell(index+2, 4, ltp)      # LTP
        sheet.update_cell(index+2, 5, rsi)      # RSI
        sheet.update_cell(index+2, 6, ema)      # EMA
        sheet.update_cell(index+2, 7, oi)       # OI
        sheet.update_cell(index+2, 9, signal)   # Final Signal

    except Exception as e:
        print(f"Error with {symbol}: {e}")

print("Sheet updated successfully.")
