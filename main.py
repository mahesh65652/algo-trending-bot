import os
import json
import requests
import gspread
import pyotp
import pandas as pd
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
spreadsheet = client.open_by_key(os.environ["GSHEET_ID"])
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
summary_rows = [["Index", "Spot LTP", "ATM Strike", "ATM CE", "ATM PE"]]
telegram_msg = "✅ ATM Options Algo Run\n"

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

        summary_rows.append([idx["name"], spot, strike, ce_ltp, pe_ltp])

        telegram_msg += f"\n{idx['name']} Spot:{spot} Strike:{strike} CE:{ce_ltp} PE:{pe_ltp}"

        # --- Daily Log Tab ---
        tab_name = f"{idx['name']}_{today.strftime('%Y-%m-%d')}"
        try:
            ws = spreadsheet.worksheet(tab_name)
        except:
            ws = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="10")
            ws.append_row(["Time", "Spot", "Strike", "CE", "PE"])

        ws.append_row([
            datetime.now().strftime("%H:%M:%S"),
            spot,
            strike,
            ce_ltp,
            pe_ltp
        ])

    except Exception as e:
        summary_rows.append([idx["name"], f"Error: {e}", "-", "-", "-"])
        telegram_msg += f"\n{idx['name']} Error: {e}"

# --- 6. Update Google Sheet (Summary Tab) ---
summary_ws = spreadsheet.sheet1
summary_ws.clear()
summary_ws.update("A1", summary_rows)

# --- 7. Telegram Alert ---
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if bot_token and chat_id:
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data={"chat_id": chat_id, "text": telegram_msg}
    )

print("✅ Strategy run completed.")

# --- 5. Fetch LTPs ---
summary_rows = [["Index", "Spot LTP", "ATM Strike", "ATM CE", "ATM PE"]]
telegram_msg = "✅ ATM Options Algo Run\n"

for idx in indices:
    try:
        # Spot LTP
        ltp_data = smart_api.ltpData("NSE", "INDICES", idx["token"])
        # ✅ सुरक्षा जांच जोड़ें
        if not ltp_data or "data" not in ltp_data or "ltp" not in ltp_data["data"]:
            raise Exception("Failed to fetch spot LTP data.")
        spot = ltp_data["data"]["ltp"]

        # ATM Strike
        strike = round(spot / idx["step"]) * idx["step"]

        # Option symbols
        ce_symbol = f"{idx['symbol']}{expiry}{strike}CE"
        pe_symbol = f"{idx['symbol']}{expiry}{strike}PE"

        # CE LTP
        ce_data = smart_api.ltpData("NFO", "OPTIDX", ce_symbol)
        # ✅ सुरक्षा जांच जोड़ें
        if not ce_data or "data" not in ce_data or "ltp" not in ce_data["data"]:
            raise Exception(f"Failed to fetch CE LTP for {ce_symbol}")
        ce_ltp = ce_data["data"]["ltp"]

        # PE LTP
        pe_data = smart_api.ltpData("NFO", "OPTIDX", pe_symbol)
        # ✅ सुरक्षा जांच जोड़ें
        if not pe_data or "data" not in pe_data or "ltp" not in pe_data["data"]:
            raise Exception(f"Failed to fetch PE LTP for {pe_symbol}")
        pe_ltp = pe_data["data"]["ltp"]

        summary_rows.append([idx["name"], spot, strike, ce_ltp, pe_ltp])
        telegram_msg += f"\n{idx['name']} Spot:{spot} Strike:{strike} CE:{ce_ltp} PE:{pe_ltp}"

        # --- Daily Log Tab ---
        tab_name = f"{idx['name']}_{today.strftime('%Y-%m-%d')}"
        try:
            ws = spreadsheet.worksheet(tab_name)
        except:
            ws = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="10")
            ws.append_row(["Time", "Spot", "Strike", "CE", "PE"])

        ws.append_row([
            datetime.now().strftime("%H:%M:%S"),
            spot,
            strike,
            ce_ltp,
            pe_ltp
        ])

    except Exception as e:
        # अब यह यहाँ अलग-अलग एरर दिखाएगा
        summary_rows.append([idx["name"], f"Error: {e}", "-", "-", "-"])
        telegram_msg += f"\n{idx['name']} Error: {e}"
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
spreadsheet = client.open_by_key(os.environ["GSHEET_ID"])
print("✅ Google Sheet connected successfully.")

# --- 2. Angel One API Connect ---
api_key     = os.environ.get("ANGEL_API_KEY")
client_code = os.environ.get("ANGEL_CLIENT_CODE")
pwd         = os.environ.get("ANGEL_CLIENT_PWD")
totp_key    = os.environ.get("ANGEL_TOTP_SECRET")

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
expiry = (today + timedelta(days=days_ahead)).strftime("%d%b%y").upper()

# --- 5. Fetch LTPs ---
summary_rows = [["Index", "Spot LTP", "ATM Strike", "ATM CE", "ATM PE"]]
telegram_msg = "✅ ATM Options Algo Run\n"

for idx in indices:
    try:
        # --- Spot LTP ---
        ltp_data = smart_api.ltpData("NSE", "INDICES", idx["token"])
        if not ltp_data or "data" not in ltp_data or "ltp" not in ltp_data["data"]:
            raise Exception("Failed to fetch Spot LTP")
        spot = ltp_data["data"]["ltp"]

        # --- ATM Strike ---
        strike = round(spot / idx["step"]) * idx["step"]

        # --- Option symbols ---
        ce_symbol = f"{idx['symbol']}{expiry}{strike}CE"
        pe_symbol = f"{idx['symbol']}{expiry}{strike}PE"

        # --- CE LTP ---
        ce_data = smart_api.ltpData("NFO", "OPTIDX", ce_symbol)
        if not ce_data or "data" not in ce_data or "ltp" not in ce_data["data"]:
            raise Exception(f"Failed to fetch CE LTP ({ce_symbol})")
        ce_ltp = ce_data["data"]["ltp"]

        # --- PE LTP ---
        pe_data = smart_api.ltpData("NFO", "OPTIDX", pe_symbol)
        if not pe_data or "data" not in pe_data or "ltp" not in pe_data["data"]:
            raise Exception(f"Failed to fetch PE LTP ({pe_symbol})")
        pe_ltp = pe_data["data"]["ltp"]

        # ✅ Add to Summary
        summary_rows.append([idx["name"], spot, strike, ce_ltp, pe_ltp])
        telegram_msg += f"\n{idx['name']} Spot:{spot} Strike:{strike} CE:{ce_ltp} PE:{pe_ltp}"

        # ✅ Daily Log Tab
        tab_name = f"{idx['name']}_{today.strftime('%Y-%m-%d')}"
        try:
            ws = spreadsheet.worksheet(tab_name)
        except:
            ws = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="10")
            ws.append_row(["Time", "Spot", "Strike", "CE", "PE"])

        ws.append_row([
            datetime.now().strftime("%H:%M:%S"),
            spot,
            strike,
            ce_ltp,
            pe_ltp
        ])

    except Exception as e:
        summary_rows.append([idx["name"], f"Error: {e}", "-", "-", "-"])
        telegram_msg += f"\n{idx['name']} Error: {e}"

# --- 6. Update Google Sheet (Summary Tab) ---
summary_ws = spreadsheet.sheet1
summary_ws.clear()
summary_ws.update("A1", summary_rows)

# --- 7. Telegram Alert ---
bot_token = os.environ.get("TELEGRAM_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if bot_token and chat_id:
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data={"chat_id": chat_id, "text": telegram_msg}
    )

print("✅ Strategy run completed.")
