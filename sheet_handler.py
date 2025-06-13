import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_signals():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("SHEET_ID").sheet1
    data = sheet.get_all_records()
    signals = []
    for row in data:
        if row["Action"] in ["BUY", "SELL"]:
            signals.append({"symbol": row["Symbol"], "action": row["Action"]})
    return signals
