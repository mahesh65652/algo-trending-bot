import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

def get_gsheet_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def batch_update_signals(worksheet, signals, col_index):
    col_letter = chr(65 + col_index)
    cell_range = f"{col_letter}2:{col_letter}{len(signals)+1}"
    values = [[s] for s in signals]
    worksheet.batch_update([{'range': cell_range, 'values': values}])
