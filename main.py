import os
import json
import requests
import gspread
import pyotp
import pandas as pd
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi import SmartConnect
from gspread.exceptions import APIError, WorksheetNotFound

# --- Function to get symbol token from master file ---
def get_symbol_token(exchange, trading_symbol):
    """
    Downloads the symbol master file and finds the symbol token for a given trading symbol.
    """
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = json.loads(response.text)
            for item in data:
                if item.get('exch_seg') == exchange and item.get('symbol') == trading_symbol:
                    return item.get('token')
            print(f"Error: Symbol '{trading_symbol}' not found on exchange '{exchange}'")
            return None
        else:
            print(f"Error: Failed to download master file. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Network error occurred while fetching symbol master file: {e}")
        return None
    except Exception as e:
        print(f"An error occurred in get_symbol_token: {e}")
        return None

# --- 1. Google Sheet Connect ---
try:
    creds_dict = json.loads(os.environ["GSHEET_CREDS_JSON"])
except Exception as e:
    raise Exception(f"❌ GSHEET_CREDS_JSON invalid: {e}")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Retry logic for 503 errors
for attempt in range(5):
    try:
        spreadsheet = client.open_by_key(os.environ["GSHEET_ID"])
        print("✅ Google Sheet connected successfully.")
        break
    except APIError as e:
        if "503" in str(e):
            wait_time = 5 * (attempt + 1)
            print(f"⚠ Google Sheets API 503 error, retrying in {wait_time} sec...")
            time.sleep(wait_time)
        else:
            raise
else:
    raise Exception("❌ Failed to connect to Google Sheets after retries.")

# --- 2. Angel One API Connect ---
api_key     = os.environ.get("ANGEL_API_KEY")
client_code = os.environ.get("ANGEL_CLIENT_CODE")
pwd         = os.environ.get("ANGEL_CLIENT_PWD")
totp_key    = os.environ.get("ANGEL_TOTP_SECRET")

if not all([api_key, client_code, pwd, totp_key]):
    raise Exception("❌ ERROR: Missing Angel One credentials in GitHub Secrets")

smart_api = SmartConnect(api_key)
try:
    totp = pyotp.TOTP(totp_key).now()
    print(f"🔑 Generated OTP: {totp}")
    data = smart_api.generateSession(client_code, pwd, totp)
    if not data.get("status"):
        raise Exception(f"Login failed: {data.get('message', 'Unknown error')}")
    print("✅ Angel One login successful.")
except Exception as e:
    raise Exception(f"❌ Angel One login failed: {e}")

# --- 3. Index data ---
indices = [
    {"name": "NIFTY", "symbol": "NIFTY", "exchange": "NSE", "step": 50},
    {"name": "BANKNIFTY", "symbol": "BANKNIFTY", "exchange": "NSE", "step": 100},
    {"name": "FINNIFTY", "symbol": "FINNIFTY", "exchange": "NSE", "step": 50},
    {"name": "MIDCPNIFTY", "symbol": "MIDCPNIFTY", "exchange": "NSE", "step": 100},
    {"name": "SENSEX", "symbol": "SENSEX", "exchange": "BSE", "step": 100},
]

# --- 4. Expiry Date (Nearest Thursday) ---
today = datetime.now()
days_ahead = (3 - today.weekday()) % 7
if days_ahead == 0:
    days_ahead = 7
expiry = (today + timedelta(days=days_ahead)).strftime("%d%b%y").upper()

# --- 5. Fetch LTPs and Update Sheets ---
summary_rows = [["Index", "Spot LTP", "ATM Strike", "ATM CE", "ATM PE"]]
telegram_msg = "✅ ATM Options Algo Run\n"

for idx in indices:
    try:
        # --- Spot LTP ---
        idx_token = get_symbol_token(idx["exchange"], idx["symbol"])
        if not idx_token:
            print(f"❌ Skipping {idx['name']}: Index token not found.")
            continue
        
        ltp_data = smart_api.ltpData(idx["exchange"], idx["symbol"], idx_token)
        if not ltp_data or "data" not in ltp_data or "ltp" not in ltp_data["data"]:
            raise Exception("Failed to fetch Spot LTP.")
        spot = ltp_data["data"]["ltp"]

        # --- ATM Strike ---
        strike = round(spot / idx["step"]) * idx["step"]

        # --- Option Symbols ---
        ce_trading_symbol = f"{idx['symbol']}{expiry}{strike}CE"
        pe_trading_symbol = f"{idx['symbol']}{expiry}{strike}PE"
        
        # --- Get Option Tokens ---
        ce_token = get_symbol_token("NFO", ce_trading_symbol)
        pe_token = get_symbol_token("NFO", pe_trading_symbol)
        
        if not ce_token or not pe_token:
            print(f"❌ Skipping {idx['name']}: Option tokens not found. Check symbol names or expiry date.")
            continue

        # --- CE LTP ---
        ce_data = smart_api.ltpData("NFO", ce_trading_symbol, ce_token)
        if not ce_data or "data" not in ce_data or "ltp" not in ce_data["data"]:
            raise Exception(f"Failed to fetch CE LTP for {ce_trading_symbol}")
        ce_ltp = ce_data["data"]["ltp"]

        # --- PE LTP ---
        pe_data = smart_api.ltpData("NFO", pe_trading_symbol, pe_token)
        if not pe_data or "data" not in pe_data or "ltp" not in pe_data["data"]:
            raise Exception(f"Failed to fetch PE LTP for {pe_trading_symbol}")
        pe_ltp = pe_data["data"]["ltp"]

        # ✅ Add to Summary and Telegram
        summary_rows.append([idx["name"], spot, strike, ce_ltp, pe_ltp])
        telegram_msg += f"\n{idx['name']} Spot:{spot} Strike:{strike} CE:{ce_ltp} PE:{pe_ltp}"

        # --- Daily Log Tab ---
        tab_name = f"{idx['name']}_{today.strftime('%Y-%m-%d')}"
        try:
            ws = spreadsheet.worksheet(tab_name)
        except WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="10")
            ws.append_row(["Time", "Spot", "Strike", "CE", "PE"])
        
        ws.append_row([
            datetime.now().strftime("%H:%M:%S"),
            spot,
            strike,
            ce_ltp,
            pe_ltp
        ])
        print(f"📊 Added row for {idx['name']} to {tab_name} sheet.")

    except Exception as e:
        summary_rows.append([idx["name"], f"Error: {e}", "-", "-", "-"])
        telegram_msg += f"\n{idx['name']} Error: {e}"
        print(f"❌ Error processing {idx['name']}: {e}")

# --- 6. Update Google Sheet (Summary Tab) ---
summary_ws = spreadsheet.sheet1
summary_ws.update("A1:E" + str(len(summary_rows)), summary_rows)
print("📊 Summary sheet updated.")

# --- 7. Telegram Alert ---
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if bot_token and chat_id:
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data={"chat_id": chat_id, "text": telegram_msg}
    )
    print("📨 Telegram alert sent.")

print("✅ Strategy run completed.")
