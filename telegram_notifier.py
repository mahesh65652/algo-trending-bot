import os
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from telegram_notifier import send_telegram_message  # ← ये आपकी ऊपर की function वाली फाइल में हो

# 1. Google Sheet से connect करें
def get_sheet_data(sheet_id):
    credentials = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_dict = eval(credentials)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data), sheet

# 2. Signal Logic
def generate_signal(row):
    if row['RSI'] < 30 and row['Price'] > row['EMA']:
        return "Buy"
    elif row['RSI'] > 70 and row['Price'] < row['EMA']:
        return "Sell"
    else:
        return "Hold"

# 3. Main Function
def main():
    SHEET_ID = os.getenv("SHEET_ID")
    df, sheet = get_sheet_data(SHEET_ID)
    
    signals = []
    messages = []

    for index, row in df.iterrows():
        signal = generate_signal(row)
        signals.append(signal)

        if signal in ["Buy", "Sell"]:
            messages.append(f"*{signal} Alert* 📢\nSymbol: `{row['Symbol']}`\nPrice: ₹{row['Price']}\nRSI: {row['RSI']}\nEMA: {row['EMA']}")

    # Update Sheet with Final Signal
    signal_range = f"H2:H{len(signals)+1}"  # Assuming column H is Final Signal
    sheet.update(signal_range, [[sig] for sig in signals])

    # Send Telegram Alerts
    for msg in messages:
        send_telegram_message(msg)

if __name__ == "__main__":
    main()
