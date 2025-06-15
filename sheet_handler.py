import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_signals():
    # 1. Access Scope
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # 2. Load credentials.json (make sure it's downloaded properly and in same folder)
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

    # 3. Connect to Google Sheet
    client = gspread.authorize(creds)
    
    # 4. Open sheet by ID (Replace with actual Sheet ID)
    sheet = client.open_by_key("1VHbKOFDL6ARr34ldlqh64h90OKLMzCsP39xBt264sl8").worksheet("mcx")

    # 5. Get all records
    data = sheet.get_all_records()

    # 6. Extract signals
    signals = []
    for row in data:
        if row.get("Action") in ["BUY", "SELL"]:
            signals.append({
                "symbol": row.get("Symbol"),
                "action": row.get("Action")
            })

    return signals
