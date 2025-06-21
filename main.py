import os
import json
# Save GOOGLE_CREDS_JSON content to credentials.json
google_creds = os.environ.get("GOOGLE_CREDS_JSON")
if google_creds:
    with open("credentials.json", "w") as f:
        f.write(google_creds)
import os
import json
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi.smartConnect import SmartConnect

# Load environment variables
load_dotenv()

# ENV Variables
api_key = os.getenv("ANGEL_API_KEY")
api_secret = os.getenv("ANGEL_API_SECRET")
client_code = os.getenv("CLIENT_CODE")
totp = os.getenv("TOTP")
sheet_id = os.getenv("SHEET_ID")

# ✅ Google Sheet Access using credentials from GitHub Secrets
def get_signals():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # 👇 Load credentials securely from GitHub Secret
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet("sheet1")  # change to your tab name if needed

    data = sheet.get_all_records()

    signals = []
    for row in data:
        if row.get("Action") in ["BUY", "SELL"]:
            signals.append({"symbol": row["Symbol"], "action": row["Action"]})
    return signals

# ✅ Angel One Login
def angel_login():
    obj = SmartConnect(api_key=api_key)
    data = obj.generateSession(client_code, api_secret, totp)
    return obj

# ✅ Place Order Function
def place_order(obj, symbol, action):
    print(f"Placing {action} order for {symbol}")
    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": "99926009",  # Replace this with dynamic token if needed
            "transactiontype": action,
            "exchange": "MCX",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": "1"
        }
        response = obj.placeOrder(orderparams)
        print("Order Response:", response)
    except Exception as e:
        print("Order Failed:", e)

# ✅ Main Runner
if __name__ == "__main__":
    signals = get_signals()
    if signals:
        angel = angel_login()
        for sig in signals:
            place_order(angel, sig["symbol"], sig["action"])
    else:
        print("No Buy/Sell Signals Found.")

