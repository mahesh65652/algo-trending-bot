import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os, json, requests, random

print("🚀 Running Algo Trading Bot...")

# ✅ Send Telegram message
def send_telegram_message(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        response = requests.post(url, data=data)
        print("📤 Telegram:", response.status_code)
    else:
        print("⚠️ Telegram token/chat_id missing")

# ✅ Google Sheet Auth
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# ✅ Open Spreadsheet
sheet_id = os.environ.get("SHEET_ID")
spreadsheet = client.open_by_key(sheet_id)
all_sheets = spreadsheet.worksheets()

# ✅ Get mock indicators
def get_indicator_values(symbol):
    price = random.randint(19000, 20000)
    rsi = random.randint(10, 90)
    ema = random.randint(19000, 20000)
    oi = random.randint(100000, 500000)
    return rsi, ema, oi, price

# ✅ Signal logic
def generate_signal(rsi, ema, price):
    if rsi < 30 and price > ema:
        return "Buy"
    elif rsi > 70 and price < ema:
        return "Sell"
    else:
        return "Hold"

# ✅ Process all tabs
for sheet in all_sheets:
    print(f"\n📄 Sheet: {sheet.title}")
    try:
        data = sheet.get_all_values()
        rows = data[1:]  # Skip header

        for i, row in enumerate(rows):
            symbol = row[0].strip()
            if not symbol: continue

            rsi, ema, oi, price = get_indicator_values(symbol)
            signal = generate_signal(rsi, ema, price)

            sheet.update_cell(i+2, 2, price)      # B = LTP
            sheet.update_cell(i+2, 3, rsi)        # C = RSI
            sheet.update_cell(i+2, 4, ema)        # D = EMA
            sheet.update_cell(i+2, 5, oi)         # E = OI
            sheet.update_cell(i+2, 6, "N/A")      # F = Price Action
            sheet.update_cell(i+2, 7, signal)     # G = Final Signal
            sheet.update_cell(i+2, 8, signal)     # H = Action

            print(f"✅ {symbol} → {signal} @ {price}")
            send_telegram_message(f"[{sheet.title}] {symbol}: {signal} @ {price} | RSI: {rsi}, EMA: {ema}, OI: {oi}")

    except Exception as e:
        print(f"❌ Error: {e}")

