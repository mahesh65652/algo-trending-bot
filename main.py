import os, json, sys

# Verify GSHEET_CREDS_JSON secret
creds_raw = os.getenv("GSHEET_CREDS_JSON")
if not creds_raw:
    sys.exit("❌ ERROR: GSHEET_CREDS_JSON secret missing!")

try:
    creds_dict = json.loads(creds_raw)
except json.JSONDecodeError:
    sys.exit("❌ ERROR: GSHEET_CREDS_JSON is not valid JSON! Please paste the full Service Account key.")

# Extra check: private_key field present and correct format
if "private_key" not in creds_dict or "-----BEGIN PRIVATE KEY-----" not in creds_dict["private_key"]:
    sys.exit("❌ ERROR: GSHEET_CREDS_JSON is incomplete or private_key is invalid.")

print("✅ Google Sheet credentials loaded successfully.")
import os, json, gspread, requests
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi import SmartConnect
import pyotp

# ==== 1. Google Sheet Connect ====
creds_dict = json.loads(os.environ['GSHEET_CREDS_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ['GSHEET_ID']).sheet1

# ==== 2. Angel One API Connect ====
api_key = os.environ['ANGEL_API_KEY']
api_secret = os.environ['ANGEL_API_SECRET']
client_code = os.environ['CLIENT_CODE']
totp_key = os.environ['TOTP']

smart_api = SmartConnect(api_key)
totp = pyotp.TOTP(totp_key).now()
data = smart_api.generateSession(client_code, totp, api_secret)

if not data.get('status'):
    raise Exception(f"Login failed: {data}")

# ==== 3. Index tokens ====
indices = [
    {"name": "NIFTY", "token": "99926000"},
    {"name": "BANKNIFTY", "token": "99926009"},
    {"name": "FINNIFTY", "token": "99926037"},
    {"name": "MIDCPNIFTY", "token": "99926064"},
    {"name": "SENSEX", "token": "99919000"}
]

# ==== 4. Fetch LTP and update sheet ====
rows = [["Index", "LTP"]]
for idx in indices:
    try:
        ltp_data = smart_api.ltpData("NSE", "INDICES", idx["token"])
        ltp = ltp_data['data']['ltp']
        rows.append([idx["name"], ltp])
    except Exception as e:
        rows.append([idx["name"], f"Error: {e}"])

# Clear & update
sheet.clear()
sheet.update("A1", rows)

# ==== 5. Telegram Alert ====
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if bot_token and chat_id:
    msg = "✅ Algo Bot executed successfully!\n" + "\n".join(f"{r[0]}: {r[1]}" for r in rows[1:])
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={"chat_id": chat_id, "text": msg})
