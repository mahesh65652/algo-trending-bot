import os
import json
import requests
import gspread
import pyotp

from oauth2client.service_account import ServiceAccountCredentials
from SmartApi import SmartConnect

# --- 1. Google Sheet Connect ---
try:
    creds_dict = json.loads(os.environ["GSHEET_CREDS_JSON"])
except Exception as e:
    raise Exception(f"❌ GSHEET_CREDS_JSON invalid: {e}")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ["GSHEET_ID"]).sheet1
print("✅ Google Sheet connected successfully.")

# --- 2. Angel One API Connect ---
api_key     = os.environ.get("ANGEL_API_KEY")
client_code = os.environ.get("CLIENT_CODE")
pwd         = os.environ.get("PASSWORD")
totp_key    = os.environ.get("TOTP")

if not all([api_key, client_code, pwd, totp_key]):
    raise Exception("❌ ERROR: Missing Angel One credentials in GitHub Secrets")

smart_api = SmartConnect(api_key)
totp = pyotp.TOTP(totp_key).now()
data = smart_api.generateSession(client_code, pwd, totp)

if not data.get("status"):
    raise Exception(f"Login failed: {data}")
print("✅ Angel One login successful.")

# --- 3. Index tokens ---
indices = [
    {"name": "NIFTY", "token": "99926000"},
    {"name": "BANKNIFTY", "token": "99926009"},
    {"name": "FINNIFTY", "token": "99926037"},
    {"name": "MIDCPNIFTY", "token": "99926064"},
    {"name": "SENSEX", "token": "99919000"},
]

# --- 4. Fetch LTP and update sheet ---
rows = [["Index", "LTP"]]
for idx in indices:
    try:
        ltp_data = smart_api.ltpData("NSE", "INDICES", idx["token"])
        ltp = ltp_data["data"]["ltp"]
        rows.append([idx["name"], ltp])
    except Exception as e:
        rows.append([idx["name"], f"Error: {e}"])

sheet.clear()
sheet.update("A1", rows)

# --- 5. Telegram Alert ---
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if bot_token and chat_id:
    msg = "✅ Algo Bot executed successfully!\n" + "\n".join(f"{r[0]}: {r[1]}" for r in rows[1:])
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={"chat_id": chat_id, "text": msg})

print("✅ Strategy run completed.")

import os
import json
import requests
import gspread
import pyotp
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi import SmartConnect

# --- 1. Google Sheet Connect ---
try:
    creds_dict = json.loads(os.environ["GSHEET_CREDS_JSON"])
except Exception as e:
    raise Exception(f"❌ GSHEET_CREDS_JSON invalid: {e}")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ["GSHEET_ID"]).sheet1
print("✅ Google Sheet connected successfully.")

# --- 2. Angel One API Connect ---
api_key     = os.environ.get("ANGEL_API_KEY")
client_code = os.environ.get("CLIENT_CODE")
pwd         = os.environ.get("PASSWORD")
totp_key    = os.environ.get("TOTP")

if not all([api_key, client_code, pwd, totp_key]):
    raise Exception("❌ ERROR: Missing Angel One credentials in GitHub Secrets")

smart_api = SmartConnect(api_key)
totp = pyotp.TOTP(totp_key).now()
data = smart_api.generateSession(client_code, pwd, totp)

if not data.get("status"):
    raise Exception(f"Login failed: {data}")
print("✅ Angel One login successful.")

# --- 3. Index tokens ---
indices = [
    {"name": "NIFTY", "token": "99926000", "symbol": "NIFTY", "step": 50},
    {"name": "BANKNIFTY", "token": "99926009", "symbol": "BANKNIFTY", "step": 100},
    {"name": "FINNIFTY", "token": "99926037", "symbol": "FINNIFTY", "step": 50},
    {"name": "MIDCPNIFTY", "token": "99926064", "symbol": "MIDCPNIFTY", "step": 100},
    {"name": "SENSEX", "token": "99919000", "symbol": "SENSEX", "step": 100},
]

# --- 4. Expiry Date (Nearest Thursday) ---
today = datetime.now()
days_ahead = (3 - today.weekday()) % 7  # Thursday = 3
if days_ahead == 0:
    days_ahead = 7
expiry = (today + timedelta(days=days_ahead)).strftime("%d%b%y").upper()  # e.g. 21AUG24

# --- 5. Fetch LTPs ---
rows = [["Index", "Spot LTP", "ATM Strike", "ATM CE", "ATM PE"]]
for idx in indices:
    try:
        # Spot LTP
        ltp_data = smart_api.ltpData("NSE", "INDICES", idx["token"])
        spot = ltp_data["data"]["ltp"]

        # ATM Strike
        strike = round(spot / idx["step"]) * idx["step"]

        # Option symbols
        ce_symbol = f"{idx['symbol']}{expiry}{strike}CE"
        pe_symbol = f"{idx['symbol']}{expiry}{strike}PE"

        ce_ltp = smart_api.ltpData("NFO", "OPTIDX", ce_symbol)["data"]["ltp"]
        pe_ltp = smart_api.ltpData("NFO", "OPTIDX", pe_symbol)["data"]["ltp"]

        rows.append([idx["name"], spot, strike, ce_ltp, pe_ltp])

    except Exception as e:
        rows.append([idx["name"], f"Error: {e}", "-", "-", "-"])

# --- 6. Update Google Sheet ---
sheet.clear()
sheet.update("A1", rows)

# --- 7. Telegram Alert ---
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if bot_token and chat_id:
    msg = "✅ ATM Options Algo Run\n"
    for r in rows[1:]:
        msg += f"\n{r[0]} Spot:{r[1]} Strike:{r[2]} CE:{r[3]} PE:{r[4]}"
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={"chat_id": chat_id, "text": msg})

print("✅ Strategy run completed.")

