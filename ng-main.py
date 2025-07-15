import pandas as pd
import yfinance as yf
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====== Google Sheet Setup ======
SHEET_ID = "1kdV2U3PUIN5MVsGVgoEX7up384Vvm2ap"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

CREDS = ServiceAccountCredentials.from_json_keyfile_name("your-json-key.json", SCOPE)
CLIENT = gspread.authorize(CREDS)

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_ema(data, period=20):
    return data['Close'].ewm(span=period, adjust=False).mean()

def fetch_data(ticker):
    df = yf.download(ticker, interval='15m', period='2d')
    df.dropna(inplace=True)
    df['RSI'] = calculate_rsi(df)
    df['EMA'] = calculate_ema(df)
    return df

def update_sheet(sheet_name, ltp, rsi, ema, price_action, signal):
    sheet = CLIENT.open_by_key(SHEET_ID).worksheet(sheet_name)
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    values = [
        [ltp],     # B2
        [rsi],     # C2
        [ema],     # D2
        [price_action], # E2
        [signal],  # F2
        ["AUTO"],  # G2
        [now]      # H2
    ]

    # Update columns from B2 to H2
    for i, val in enumerate(values):
        sheet.update_cell(2, i+2, val[0])

def get_final_signal(rsi, close, ema):
    if rsi > 60 and close > ema:
        return "BUY"
    elif rsi < 40 and close < ema:
        return "SELL"
    else:
        return "HOLD"

def main():
    symbols = {
        "CRUDEOIL": "CRUDEOIL.NS",
        "NG": "NATURALGAS.NG"
    }

    for sheet_name, ticker in symbols.items():
        df = fetch_data(ticker)
        last = df.iloc[-1]
        ltp = round(last['Close'], 2)
        rsi = round(last['RSI'], 2)
        ema = round(last['EMA'], 2)
        price_action = "Above EMA" if ltp > ema else "Below EMA"
        signal = get_final_signal(rsi, ltp, ema)

        update_sheet(sheet_name, ltp, rsi, ema, price_action, signal)

if __name__ == "__main__":
    main()

