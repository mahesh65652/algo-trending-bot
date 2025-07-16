import os
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from nsepython import *
import ta

# ✅ Google Sheet Auth
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
client = gspread.authorize(creds)

# ✅ Sheet Access
sheet_id = "1lZFDzjEFCqYuek9W5APaZ6lFeZayITdu"
sheet_name = "BANKNIFTY"
sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
data = sheet.get_all_records()
df = pd.DataFrame(data)

# ✅ Indicator Calculation
def calculate_indicators(symbol):
    try:
        # EX: BANKNIFTY24JUL47000CE
        candles = nsefetch(f"https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY")
        # You can adjust here to get historical OHLC from your source
        
        # Dummy data just to simulate:
        ohlc = pd.DataFrame({
            "open": [46000]*20,
            "high": [46100]*20,
            "low": [45900]*20,
            "close": [46050 + i for i in range(20)],
        })

        ohlc["EMA"] = ta.trend.ema_indicator(ohlc["close"], window=14)
        ohlc["RSI"] = ta.momentum.rsi(ohlc["close"], window=14)

        latest = ohlc.iloc[-1]
        return latest["close"], latest["RSI"], latest["EMA"], 0  # OI = 0 placeholder

    except Exception as e:
        print(f"⚠️ {symbol} Error: {e}")
        return 0, 50, 0, 0

# ✅ Update Logic
final_signals = []

for i, row in df.iterrows():
    symbol = row["Symbol"]
    ltp, rsi, ema, oi = calculate_indicators(symbol)

    # Signal Logic
    signal_rsi = "Buy" if rsi < 30 else "Sell" if rsi > 70 else "Hold"
    signal_ema = "Buy" if ltp > ema else "Sell" if ltp < ema else "Hold"
    signal_oi = "Hold"  # अभी dummy

    # Final Signal
    votes = [signal_rsi, signal_ema, signal_oi]
    final = "Buy" if votes.count("Buy") >= 2 else "Sell" if votes.count("Sell") >= 2 else "Hold"
    final_signals.append({
        "LTP": round(ltp, 2),
        "RSI": round(rsi, 2),
        "EMA": round(ema, 2),
        "OI": oi,
        "Final Signal": final,
        "Action": final
    })

    print(f"{symbol} → LTP: {ltp}, RSI: {rsi}, EMA: {ema} → Final: {final}")

# ✅ Update Sheet
for idx, sig in enumerate(final_signals):
    sheet.update_cell(idx + 2, df.columns.get_loc("LTP") + 1, sig["LTP"])
    sheet.update_cell(idx + 2, df.columns.get_loc("RSI") + 1, sig["RSI"])
    sheet.update_cell(idx + 2, df.columns.get_loc("EMA") + 1, sig["EMA"])
    sheet.update_cell(idx + 2, df.columns.get_loc("OI") + 1, sig["OI"])
    sheet.update_cell(idx + 2, df.columns.get_loc("Final Signal") + 1, sig["Final Signal"])
    sheet.update_cell(idx + 2, df.columns.get_loc("Action") + 1, sig["Action"])

print("✅ BANKNIFTY Sheet Updated")
