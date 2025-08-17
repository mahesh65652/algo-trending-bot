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
