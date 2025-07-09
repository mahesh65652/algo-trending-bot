
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# Google Sheet credentials and setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

# Control sheet URL
sheet_url = "https://docs.google.com/spreadsheets/d/1kdV2U3PUIN5MVsGVgoEX7up384Vvm2ap/edit#gid=0"
spreadsheet = client.open_by_url(sheet_url)
control_sheet = spreadsheet.worksheet("Control")

def calculate_signal(rsi, ema, oi, price_action):
    if rsi < 30 and price_action == "Bullish":
        return "BUY"
    elif rsi > 70 and price_action == "Bearish":
        return "SELL"
    return "HOLD"

def update_signals():
    control_data = control_sheet.get_all_records()
    for row in control_data:
        symbol = row["Symbol"]
        target_sheet = spreadsheet.worksheet(symbol)
        data = target_sheet.get_all_records()

        for i, entry in enumerate(data):
            rsi = float(entry["RSI"])
            ema = float(entry["EMA"])
            oi = float(entry["OI"])
            price_action = entry["Price Action"]

            final_signal = calculate_signal(rsi, ema, oi, price_action)
            target_sheet.update_cell(i+2, 7, final_signal)  # Column G = "Final Signal"
            target_sheet.update_cell(i+2, 8, final_signal)  # Column H = "Action"

if __name__ == "__main__":
    update_signals()
