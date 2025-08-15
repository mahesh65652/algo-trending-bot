main.py

import os
import json
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Fixed Indices List
INDEX_LIST = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]

# Angel One API URLs
LOGIN_URL = "https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword"
SESSION_URL = "https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/generateSession"
LTP_URL = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/market/v1/quote"

def get_google_sheet_client():
    """Authorize Google Sheets API client."""
    creds_json = os.environ['GOOGLE_CREDENTIALS_JSON']
    creds_dict = json.loads(creds_json)

    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def angel_one_login():
    """Login to Angel One and return JWT token."""
    api_key = os.environ['ANGEL_API_KEY']
    api_secret = os.environ['ANGEL_API_SECRET']
    client_code = os.environ['CLIENT_CODE']
    totp = os.environ['TOTP']

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-PrivateKey": api_key
    }

    payload = {
        "clientcode": client_code,
        "password": api_secret,
        "totp": totp
    }

    resp = requests.post(LOGIN_URL, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("data") or not data["data"].get("jwtToken"):
        raise RuntimeError("Angel One login failed!")

    return data["data"]["jwtToken"]

def get_ltp(jwt_token, symbol):
    """Fetch LTP for given index from Angel One."""
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-PrivateKey": os.environ['ANGEL_API_KEY']
    }

    # Token mapping (example - replace with correct tokens)
    token_map = {
        "NIFTY": "99926000",
        "BANKNIFTY": "99926009",
        "FINNIFTY": "99926037",
        "MIDCPNIFTY": "99926062",
        "SENSEX": "1"
    }

    payload = {
        "mode": "LTP",
        "exchangeTokens": {"NSE": [token_map[symbol]]}
    }

    resp = requests.post(LTP_URL, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()

    try:
        ltp = data["data"]["fetched"][0]["ltp"]
    except Exception:
        ltp = None
    return ltp

def update_google_sheet(data_list):
    """Update Google Sheet with index data."""
    gsheet_id = os.environ['GSHEET_ID']
    client = get_google_sheet_client()
    sheet = client.open_by_key(gsheet_id).sheet1

    sheet.clear()
    sheet.append_row(["Index", "LTP", "Timestamp"])
    for row in data_list:
        sheet.append_row(row)

def send_telegram_message(message):
    """Send status to Telegram."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message})

def run():
    print("🚀 Running Auto Google Sheet Filler for Indices...")
    try:
        jwt_token = angel_one_login()
        result_data = []
        for index in INDEX_LIST:
            ltp = get_ltp(jwt_token, index)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result_data.append([index, ltp, ts])
            print(f"{index}: {ltp}")

        update_google_sheet(result_data)
        send_telegram_message("✅ Sheet updated successfully with latest index LTPs.")
        print("✅ Completed successfully.")

    except Exception as e:
        send_telegram_message(f"⚠️ Bot failed: {e}")
        raise

if __name__ == "__main__":
    run()
