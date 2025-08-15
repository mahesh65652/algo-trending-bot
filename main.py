import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi import SmartConnect
import time
import requests

# ==== CONFIG ====
TOKEN_MAP = {
    "NIFTY": "99926000",        # Nifty 50
    "BANKNIFTY": "99926007",    # Nifty Bank
    "FINNIFTY": "99926037",     # Nifty Financial Services
    "MIDCPNIFTY": "99926062",   # Nifty Midcap Select
    "SENSEX": "1"               # BSE Sensex
}
EXCHANGE = {
    "SENSEX": "BSE",
    "NIFTY": "NSE",
    "BANKNIFTY": "NSE",
    "FINNIFTY": "NSE",
    "MIDCPNIFTY": "NSE"
}

# ==== GOOGLE SHEET AUTH ====
def get_gsheet():
    creds_json = os.environ.get("GSHEET_CREDS_JSON")
    if not creds_json:
        raise Exception("❌ Missing GSHEET_CREDS_JSON in secrets")
    creds_dict = eval(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ["GSHEET_ID"]).sheet1
    return sheet

# ==== ANGEL ONE LOGIN ====
def angel_login():
    api_key = os.environ["ANGEL_API_KEY"]
    api_secret = os.environ["ANGEL_API_SECRET"]
    client_code = os.environ["CLIENT_CODE"]
    totp = os.environ["TOTP"]

    obj = SmartConnect(api_key=api_key)
    data = obj.generateSession(client_code, totp, api_secret)
    if "data" not in data:
        raise Exception(f"Login failed: {data}")
    return obj

# ==== FETCH LTP ====
def fetch_ltp(obj, symbol):
    token = TOKEN_MAP[symbol]
    exch = EXCHANGE[symbol]
    try:
        data = obj.ltpData(exch, "INDEX", token)
        return data["data"]["ltp"]
    except Exception as e:
        return None

# ==== MAIN RUN ====
def run():
    print("🚀 Starting Algo Bot for fixed indices...")
    sheet = get_gsheet()
    obj = angel_login()

    results = [["Symbol", "Token", "Exchange", "LTP", "Timestamp"]]
    for sym in TOKEN_MAP:
        ltp = fetch_ltp(obj, sym)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        results.append([sym, TOKEN_MAP[sym], EXCHANGE[sym], ltp, ts])
        print(f"📊 {sym}: {ltp}")

    # Overwrite sheet
    sheet.clear()
    sheet.update(results)
    print("✅ Sheet updated successfully!")

    send_telegram("✅ Algo Bot executed successfully!")

# ==== TELEGRAM ALERT ====
def send_telegram(msg):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": msg})

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        err_msg = f"⚠️ Algo Bot failed: {e}"
        print(err_msg)
        send_telegram(err_msg)
