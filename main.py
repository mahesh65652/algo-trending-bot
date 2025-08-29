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
import time
from datetime import datetime, timedelta
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

# --- CONFIGURATION ---
GSHEET_ID = os.getenv("GSHEET_ID")
SHEET_NAME = "LIVE DATA"
TRADE_JOURNAL_SHEET = "TRADE JOURNAL"
LIVE_TRADING = os.getenv("LIVE_TRADING", "false").strip().lower() in ("1", "true", "yes")
ORDER_QTY = int(os.getenv("ORDER_QTY", "1"))
PRODUCT_TYPE = os.getenv("PRODUCT_TYPE", "MIS")
MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
SLEEP_SECONDS = 900  # Run every 15 minutes

# To prevent duplicate orders
current_positions = {}

# --- UTILITY FUNCTIONS ---
def send_telegram_message(msg, gs_client=None):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        logging.warning("Telegram credentials missing. Skipping message.")
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
        data = sheet.get_all_records()
        if not data:
            logging.info(f"Google Sheet '{sheet_name}' is empty or has no data rows.")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df.columns = df.columns.str.upper()
        
        if 'SYMBOL' not in df.columns:
            logging.error("❌ 'SYMBOL' column not found in Google Sheet. Please check the header name.")
            return pd.DataFrame()
        
        logging.info(f"Google Sheet data from '{sheet_name}' read successful.")
        return df
    except WorksheetNotFound:
        logging.warning(f"Worksheet '{sheet_name}' not found. Skipping.")
        return pd.DataFrame()
    except Exception as e:
        logging.error(f"Google Sheet data read failed for '{sheet_name}': {e}")
        return pd.DataFrame()

def update_google_sheet_cell(client, sheet_id, sheet_name, cell, content):
    try:
        ws = client.open_by_key(sheet_id).worksheet(sheet_name)
        if isinstance(content, list):
            ws.update(values=content, range_name=cell)
        else:
            ws.update(values=[[content]], range_name=cell)
        logging.info(f"Sheet '{sheet_name}' updated at cell {cell}.")
    except Exception as e:
        logging.error(f"Sheet update failed for '{sheet_name}': {e}")

def update_trading_journal(client, sheet_id, trade_record):
    try:
        spreadsheet = client.open_by_key(sheet_id)
        try:
            journal_sheet = spreadsheet.worksheet(TRADE_JOURNAL_SHEET)
        except WorksheetNotFound:
            logging.info(f"Creating new worksheet '{TRADE_JOURNAL_SHEET}'.")
            journal_sheet = spreadsheet.add_worksheet(title=TRADE_JOURNAL_SHEET, rows="100", cols="6")
            journal_sheet.append_row(['TIMESTAMP', 'SYMBOL', 'ACTION', 'QUANTITY', 'PRICE', 'ORDER_ID'])
        
        journal_sheet.append_row(trade_record)
        logging.info(f"Trade record added to '{TRADE_JOURNAL_SHEET}'.")
    except Exception as e:
        logging.error(f"Failed to update trading journal: {e}")

def fetch_historical_data(api, symbol, token_info, days=30):
    try:
        if not api:
            logging.warning("API is not logged in. Skipping historical data fetch.")
            return pd.DataFrame()
        
        if not token_info or not token_info.get('token') or not token_info.get('exch_seg'):
            logging.error(f"Invalid token_info for {symbol}: {token_info}")
            return pd.DataFrame()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        params = {
            "exchange": token_info.get('exch_seg'),
            "symboltoken": token_info.get('token'),
            "interval": "ONE_DAY",
            "fromdate": start_date.strftime("%Y-%m-%d %H:%M"),
            "todate": end_date.strftime("%Y-%m-%d %H:%M")
        }
        
        historical_data = api.getCandleData(params)
        
        if not historical_data or 'data' not in historical_data or not historical_data['data']:
            logging.warning(f"No historical data found for {symbol}. Raw response: {historical_data}")
            return pd.DataFrame()
        
        df_hist = pd.DataFrame(historical_data['data'], columns=["date", "open", "high", "low", "close", "volume"])
        df_hist['close'] = pd.to_numeric(df_hist['close'])
        
        logging.info(f"Successfully fetched {len(df_hist)} data points for {symbol}.")
        return df_hist
    except Exception as e:
        logging.error(f"Failed to fetch historical data for {symbol}: {e}")
        return pd.DataFrame()

def get_live_prices_and_update_sheet(api, symbols_df, gs_client, sheet_id, sheet_name):
    if not api:
        logging.warning("Angel One API not logged in. Skipping live price fetch.")
        return False
    
    required_cols = ['SYMBOL', 'symboltoken', 'exch_seg']
    if not all(col in symbols_df.columns for col in required_cols):
        logging.error("Required columns for price fetch are missing.")
        return False

    try:
        ws = gs_client.open_by_key(sheet_id).worksheet(sheet_name)
    except Exception as e:
        logging.error(f"Failed to open worksheet for price update: {e}")
        return False

    prices_to_update = []
    
    for _, row in symbols_df.iterrows():
        try:
            ltp_data = api.ltpData(
                exchange=row['exch_seg'],
                tradingsymbol=row['SYMBOL'],
                symboltoken=row['symboltoken']
            )
            
            if ltp_data and 'data' in ltp_data and 'ltp' in ltp_data['data']:
                price = ltp_data['data']['ltp']
                prices_to_update.append([price])
                logging.info(f"Fetched LTP for {row['SYMBOL']}: {price}")
            else:
                prices_to_update.append([""])
                logging.warning(f"Failed to fetch LTP for {row['SYMBOL']}.")
            time.sleep(0.2)
        except Exception as e:
            prices_to_update.append([""])
            logging.error(f"Error fetching LTP for {row['SYMBOL']}: {e}")

    if prices_to_update:
        try:
            ws.update(values=prices_to_update, range_name=f'B2:B{1 + len(prices_to_update)}')
            logging.info(f"Successfully updated 'CLOSE' column with {len(prices_to_update)} prices.")
        except Exception as e:
            logging.error(f"Failed to update 'CLOSE' column in sheet: {e}")
            return False
    return True

def fetch_and_save_tokens():
    try:
        logging.info(f"🔄 Downloading master scrip from {MASTER_URL} ...")
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
        df["symbol"] = df["symbol"].str.upper()
        df["name"] = df["name"].str.upper()

        indices_list = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']
        indices_pattern = '|'.join([re.escape(i) for i in indices_list] + ['NIFTY 50', 'NIFTY BANK', 'NIFTY FINANCIAL SERVICES', 'NIFTY MIDCAP 100'])

        filtered_df = df[
            (df['exch_seg'].isin(['NFO', 'BSE', 'NSE', 'MCX'])) & 
            ((df['name'].str.contains(indices_pattern, regex=True, na=False)) |
            (df['instrumenttype'].isin(["OPTCOM", "FUTCOM", "FUTIDX", "EQ"])))
        ].copy()

        if filtered_df.empty:
            logging.error("❌ Filtered dataframe is empty. No tokens found.")
            return {}

        final_tokens = {}
        for _, row in filtered_df.iterrows():
            if 'tradingsymbol' not in row:
                continue

            if 'NIFTY 50' in row['name']:
                final_tokens['NIFTY'] = row.to_dict()
            elif 'NIFTY BANK' in row['name']:
                final_tokens['BANKNIFTY'] = row.to_dict()
            elif 'NIFTY FINANCIAL SERVICES' in row['name']:
                final_tokens['FINNIFTY'] = row.to_dict()
            elif 'NIFTY MIDCAP 100' in row['name']:
                final_tokens['MIDCPNIFTY'] = row.to_dict()
            elif 'SENSEX' in row['name']:
                final_tokens['SENSEX'] = row.to_dict()
            else:
                final_tokens[row['tradingsymbol']] = row.to_dict()
        
        with open('tokens.json', 'w') as f:
            json.dump(final_tokens, f, indent=4)
        
        logging.info("✅ Tokens successfully saved to tokens.json")
        logging.info(f"Saved {len(final_tokens)} tokens.")
        return final_tokens

    except Exception as e:
        logging.error(f"❌ Error fetching or saving tokens: {e}")
        return {}

def get_tokens():
    try:
        with open('tokens.json', 'r') as f:
            data = json.load(f)
        
        logging.info("✅ Successfully loaded tokens from local file.")
        return data
    except FileNotFoundError:
        logging.warning("⚠️ 'tokens.json' not found. Fetching from API...")
        return fetch_and_save_tokens()
    except Exception as e:
        logging.error(f"❌ Error reading local tokens file: {e}")
        return {}

def calculate_indicators(df):
    try:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df = df.dropna(subset=['close'])
        
        if len(df) < 26:
            logging.warning("Not enough data to calculate indicators (min 26 required for MACD).")
            return pd.DataFrame()

        # SMA Calculation (5 and 20 periods)
        df["SMA_5"] = df["close"].rolling(window=5, min_periods=1).mean()
        df["SMA_20"] = df["close"].rolling(window=20, min_periods=1).mean()

        # PCR Calculation
        if "PUT_VOLUME" in df.columns and "CALL_VOLUME" in df.columns:
            df["PUT_VOLUME"] = pd.to_numeric(df["PUT_VOLUME"], errors='coerce').fillna(0)
            df["CALL_VOLUME"] = pd.to_numeric(df["CALL_VOLUME"], errors='coerce').fillna(0)
            df["PCR"] = df["PUT_VOLUME"] / df["CALL_VOLUME"].replace(0, 1)
        else:
            df["PCR"] = np.nan
            logging.warning("Put/Call Volume data not found in Google Sheet. PCR will be NaN.")

        # RSI Calculation
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = np.where(loss == 0, np.inf, gain / loss)
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD Calculation
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['SIGNAL_LINE'] = df['MACD'].ewm(span=9, adjust=False).mean()

        logging.info("Indicators calculated: SMA, PCR, RSI and MACD.")
        return df
    except Exception as e:
        logging.error(f"Indicator calculation failed: {e}")
        return pd.DataFrame()

def generate_signals(df):
    signals = []
    if not df.empty:
        latest = df.groupby("SYMBOL").tail(1).reset_index(drop=True)
        for _, r in latest.iterrows():
            if pd.isna(r.get('MACD', np.nan)) or pd.isna(r.get('SIGNAL_LINE', np.nan)) or \
               pd.isna(r.get('RSI', np.nan)) or pd.isna(r.get('SMA_5', np.nan)) or \
               pd.isna(r.get('SMA_20', np.nan)):
                continue

            # BULLISH SIGNAL (BUY)
            if (r['SMA_5'] > r['SMA_20'] and 
                r['MACD'] > r['SIGNAL_LINE'] and 
                r['RSI'] > 60 and 
                (pd.isna(r['PCR']) or r['PCR'] < 0.75)):
                signals.append(f"BUY {r['SYMBOL']} (Multi-Indicator)")

            # BEARISH SIGNAL (SELL)
            elif (r['SMA_5'] < r['SMA_20'] and 
                  r['MACD'] < r['SIGNAL_LINE'] and 
                  r['RSI'] < 40 and 
                  (pd.isna(r['PCR']) or r['PCR'] > 1.10)):
                signals.append(f"SELL {r['SYMBOL']} (Multi-Indicator)")
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

def place_order(api, symbol, side, token_info, quantity, gs_client=None):
    if not api:
        logging.info(f"Dry-run: Would have placed a {side} order for {symbol} with quantity {quantity}.")
        return

    # Prevent duplicate orders
    current_action = current_positions.get(symbol, None)
    if current_action == side:
        logging.info(f"Skipping {side} order for {symbol}. Position is already {side}.")
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
            "quantity": quantity
        }
        order_id = api.placeOrder(order_params)
        logging.info(f"Order for {symbol} placed successfully. Order ID: {order_id}")
        
        # Update trading journal
        current_price = 0
        try:
            ltp_data = api.ltpData(
                exchange=token_info['exch_seg'],
                tradingsymbol=symbol,
                symboltoken=token_info['token']
            )
            if ltp_data and 'data' in ltp_data and 'ltp' in ltp_data['data']:
                current_price = ltp_data['data']['ltp']
        except Exception:
            pass

        trade_record = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol,
            side,
            quantity,
            current_price,
            order_id
        ]
        update_trading_journal(gs_client, GSHEET_ID, trade_record)
        
        # Update current position status
        current_positions[symbol] = side

    except Exception as e:
        logging.error(f"Order placement failed for {symbol}: {e}")
        if gs_client:
            try:
                ws = gs_client.open_by_key(GSHEET_ID).worksheet(SHEET_NAME)
                ws.update("I2", f"⚠️ Order Failed {symbol}")
            except Exception as ee:
                logging.error(f"Sheet update failed for Order error: {ee}")

# --- MAIN EXECUTION ---
def run_bot():
    logging.info("Starting trading bot run.")
    
    gs_client = get_google_sheet_client()
    if not gs_client:
        return

    angel_api = angel_login()
    tokens = get_tokens()
    
    if not tokens:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "⚠️ Token data not fetched from API")
        return

    df_sheet = read_google_sheet_data(gs_client, GSHEET_ID, SHEET_NAME)
    if df_sheet.empty:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "⚠️ Google Sheet empty or invalid")
        return

    df_sheet['SYMBOL'] = df_sheet['SYMBOL'].astype(str).str.strip().str.upper()

    df_sheet['token_info'] = df_sheet['SYMBOL'].apply(lambda s: tokens.get(s))
    df_sheet = df_sheet.dropna(subset=['SYMBOL', 'token_info'])

    if not df_sheet.empty and angel_api:
        get_live_prices_and_update_sheet(angel_api, df_sheet, gs_client, GSHEET_ID, SHEET_NAME)
    
    df_updated_sheet = read_google_sheet_data(gs_client, GSHEET_ID, SHEET_NAME)
    if df_updated_sheet.empty:
        logging.error("Failed to re-read updated sheet data.")
        return

    required_sheet_cols = ["SYMBOL", "CLOSE"]
    missing_cols = [col for col in required_sheet_cols if col not in df_updated_sheet.columns]
    if missing_cols:
        error_msg = f"❌ Error: Missing required columns in Google Sheet: {', '.join(missing_cols)}. Please ensure all required headers exist."
        logging.error(error_msg)
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", error_msg)
        return

    full_df = pd.DataFrame()
    for symbol in df_updated_sheet['SYMBOL'].unique():
        token_info = tokens.get(symbol)
        if token_info:
            hist_df = fetch_historical_data(angel_api, symbol, token_info, days=30)
            if not hist_df.empty:
                hist_df['SYMBOL'] = symbol
                full_df = pd.concat([full_df, hist_df], ignore_index=True)

    if 'PUT_VOLUME' in df_updated_sheet.columns and 'CALL_VOLUME' in df_updated_sheet.columns:
        sheet_volume_df = df_updated_sheet[['SYMBOL', 'PUT_VOLUME', 'CALL_VOLUME']].copy()
        full_df = full_df.merge(sheet_volume_df, on='SYMBOL', how='left')

    if full_df.empty:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "❌ Failed to fetch historical data.")
        send_telegram_message("❌ Error: Failed to fetch historical data. Cannot calculate indicators.")
        return

    df_with_indicators = calculate_indicators(full_df)
    
    if df_with_indicators.empty:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "❌ Indicator calculation failed. Not enough data.")
        logging.error("Exiting due to failed indicator calculation.")
        send_telegram_message("❌ Error: Indicator calculation failed. Not enough data.")
        return
        
    signals = generate_signals(df_with_indicators)
    logging.info(f"Generated signals: {signals}")

    if signals:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", [[s] for s in signals])
        send_telegram_message("📣 New Signals:\n" + "\n".join(signals), gs_client)

        for s in signals:
            parts = s.split()
            if len(parts) < 2: continue
            side, symbol = parts[0], parts[1]
            info = tokens.get(symbol)
            if info:
                try:
                    quantity_from_sheet = df_updated_sheet[df_updated_sheet['SYMBOL'] == symbol]['QUANTITY'].iloc[0]
                    order_quantity = int(quantity_from_sheet)
                except (KeyError, IndexError, ValueError):
                    logging.warning(f"Quantity column not found or invalid for {symbol}. Using default quantity: {ORDER_QTY}")
                    order_quantity = ORDER_QTY
                
                place_order(angel_api, info['tradingsymbol'], side, info, order_quantity, gs_client)
            else:
                logging.warning(f"Token not found for {symbol}.")
    else:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "No signals generated.")
        send_telegram_message("ℹ️ No trading signals generated in this run.", gs_client)
    
    logging.info("Bot run completed.")

if __name__ == "__main__":
    while True:
        try:
            run_bot()
            logging.info(f"Sleeping for {SLEEP_SECONDS} seconds...")
            time.sleep(SLEEP_SECONDS)
        except Exception as e:
            logging.error(f"An unexpected error occurred in the main loop: {e}")
            send_telegram_message(f"❌ Critical Error: Bot crashed! Restarting in 60 seconds. Error: {e}")
            time.sleep(60)
