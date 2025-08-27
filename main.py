#!/usr/bin/env python3
import os
import requests
import pandas as pd
import numpy as np
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi import SmartConnect
import pyotp
import logging
from pathlib import Path
import sys
from gspread.exceptions import WorksheetNotFound, APIError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

# --- CONFIGURATION ---
GSHEET_ID = os.getenv("GSHEET_ID")
SHEET_NAME = "LIVE DATA"
LIVE_TRADING = os.getenv("LIVE_TRADING", "false").strip().lower() in ("1", "true", "yes")
ORDER_QTY = int(os.getenv("ORDER_QTY", "1"))
PRODUCT_TYPE = os.getenv("PRODUCT_TYPE", "MIS")
MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

# NSE index symbols to track
NSE_INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]

# --- UTILITY FUNCTIONS ---
def send_telegram_message(msg, gs_client=None):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        logging.warning("Telegram credentials missing.")
        return False
    try:
        requests.post(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data={"chat_id": chat, "text": msg},
            timeout=10,
        )
        logging.info("Telegram message sent successfully.")
        return True
    except Exception as e:
        logging.error(f"Telegram message failed: {e}")
        if gs_client:
            try:
                ws = gs_client.open_by_key(GSHEET_ID).worksheet(SHEET_NAME)
                ws.update("H2", "⚠️ Telegram Failed")
            except Exception as ee:
                logging.error(f"Sheet update failed for Telegram error: {ee}")
        return False

def get_google_sheet_client():
    try:
        scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        return gspread.authorize(creds)
    except Exception as e:
        logging.error(f"Failed to authorize Google Sheet client: {e}")
        return None

def read_google_sheet_data(client, sheet_id, sheet_name):
    try:
        sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
        # Updated to include 'EXCHANGE' in expected headers
        data = sheet.get_all_records(expected_headers=["SYMBOL", "CLOSE", "EXCHANGE"])
        logging.info(f"Google Sheet data from '{sheet_name}' read successful.")
        return data
    except WorksheetNotFound:
        logging.warning(f"Worksheet '{sheet_name}' not found. Skipping.")
        return None
    except Exception as e:
        logging.error(f"Google Sheet data read failed for '{sheet_name}': {e}")
        return None

def update_google_sheet_cell(client, sheet_id, sheet_name, cell, content):
    try:
        ws = client.open_by_key(sheet_id).worksheet(sheet_name)
        if isinstance(content, list):
            content = [content]
        else:
            content = [[content]]
        ws.update(content, cell)
        logging.info(f"Sheet '{sheet_name}' updated at cell {cell}.")
    except Exception as e:
        logging.error(f"Sheet update failed for '{sheet_name}': {e}")

def get_tokens_from_api():
    try:
        logging.info(f"🔄 Downloading master from {MASTER_URL} ...")
        r = requests.get(MASTER_URL, timeout=60)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "data" in data:
            records = data["data"]
        elif isinstance(data, list):
            records = data
        else:
            logging.error("❌ Unexpected master JSON structure.")
            return {}

        df = pd.DataFrame(records)
        # Filter for both Index and Stock Futures and Options
        keep = df[
            (df["exch_seg"] == "NFO") & (df["instrumenttype"].isin(["OPTIDX", "FUTIDX", "OPTSTK", "FUTSTK"]))
        ].copy()
        
        if keep.empty:
            logging.error("❌ Filtered dataframe is empty. No tokens found.")
            return {}

        keep["symbol"] = keep["symbol"].str.upper()
        keep = keep.sort_values(["exch_seg", "symbol"])
        return keep.set_index("symbol").to_dict("index")
    except Exception as e:
        logging.error(f"❌ Error fetching tokens from API: {e}")
        return {}

def calculate_indicators(df):
    try:
        df = df.replace("", np.nan).dropna(subset=["SYMBOL", "CLOSE"])
        df['CLOSE'] = pd.to_numeric(df['CLOSE'], errors='coerce')
        df = df.dropna(subset=['CLOSE'])
        
        delta = df['CLOSE'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        exp1 = df['CLOSE'].ewm(span=12, adjust=False).mean()
        exp2 = df['CLOSE'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['SIGNAL_LINE'] = df['MACD'].ewm(span=9, adjust=False).mean()

        logging.info("Indicators calculated: RSI and MACD.")
        return df
    except Exception as e:
        logging.error(f"Indicator calculation failed: {e}")
        return pd.DataFrame()

def generate_signals(df):
    signals = []
    if not df.empty:
        if len(df) < 30:
            logging.info("Not enough data to generate signals.")
            return []

        latest = df.groupby("SYMBOL").tail(1).reset_index(drop=True)
        for _, r in latest.iterrows():
            if pd.to_numeric(r['MACD']) > pd.to_numeric(r['SIGNAL_LINE']) and pd.to_numeric(r['RSI']) > 50:
                signals.append(f"BUY {r['SYMBOL']} (MACD Crossover)")
            elif pd.to_numeric(r['MACD']) < pd.to_numeric(r['SIGNAL_LINE']) and pd.to_numeric(r['RSI']) < 50:
                signals.append(f"SELL {r['SYMBOL']} (MACD Crossover)")
    return signals

def angel_login():
    if not LIVE_TRADING:
        logging.info("Live trading is off. Skipping Angel login.")
        return None
    try:
        api = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
        api.generateSession(
            os.getenv("ANGEL_CLIENT_CODE"),
            os.getenv("ANGEL_CLIENT_PWD"),
            totp
        )
        logging.info("Angel One login successful.")
        return api
    except Exception as e:
        logging.error(f"Angel login failed: {e}")
        return None

def place_order(api, symbol, side, token_info, gs_client=None):
    if not api:
        logging.info(f"Dry-run: Would have placed a {side} order for {symbol}.")
        return

    try:
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token_info['token'],
            "transactiontype": side,
            "ordertype": "MARKET",
            "producttype": PRODUCT_TYPE,
            "exchange": token_info['exch_seg'],
            "quantity": ORDER_QTY
        }
        order_id = api.placeOrder(order_params)
        logging.info(f"Order for {symbol} placed successfully. Order ID: {order_id}")
    except Exception as e:
        logging.error(f"Order placement failed for {symbol}: {e}")
        if gs_client:
            try:
                ws = gs_client.open_by_key(GSHEET_ID).worksheet(SHEET_NAME)
                ws.update("I2", f"⚠️ Order Failed {symbol}")
            except Exception as ee:
                logging.error(f"Sheet update failed for Order error: {ee}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    logging.info("Starting trading bot run.")
    
    gs_client = get_google_sheet_client()
    if not gs_client:
        exit(1)

    angel_api = angel_login()
    
    tokens = get_tokens_from_api()
    if not tokens:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "⚠️ Token data not fetched")
        exit(1)

    sheet_data = read_google_sheet_data(gs_client, GSHEET_ID, SHEET_NAME)
    if not sheet_data:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "⚠️ Google Sheet empty or invalid")
        exit(1)

    df = pd.DataFrame(sheet_data)
    df = df[df['SYMBOL'].isin(NSE_INDEX_SYMBOLS)]
    if df.empty:
        logging.info("No NSE index symbols found in the Google Sheet data. Exiting.")
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "No NSE index symbols found.")
        exit(0)

    df['instrumenttype'] = df['SYMBOL'].apply(lambda s: tokens.get(s, {}).get('instrumenttype'))
    df['exch_seg'] = df['SYMBOL'].apply(lambda s: tokens.get(s, {}).get('exch_seg'))
    df = df.dropna(subset=['instrumenttype', 'exch_seg'])

    df = calculate_indicators(df)
    signals = generate_signals(df)
    logging.info(f"Generated signals: {signals}")

    if signals:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "\n".join(signals))
        send_telegram_message("📣 New Signals:\n" + "\n".join(signals), gs_client)

        for s in signals:
            parts = s.split()
            if len(parts) < 2: continue
            side, symbol = parts[0], parts[1]
            info = tokens.get(symbol)
            if info:
                place_order(angel_api, symbol, side, info, gs_client)
            else:
                logging.warning(f"Token not found for {symbol}.")
    else:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "No signals generated.")
        send_telegram_message("ℹ️ No trading signals generated in this run.", gs_client)
    
    logging.info("Bot run completed.")
