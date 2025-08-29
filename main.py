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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

# --- CONFIGURATION ---
GSHEET_ID = os.getenv("GSHEET_ID")
SHEET_NAME = "LIVE DATA"
LIVE_TRADING = os.getenv("LIVE_TRADING", "false").strip().lower() in ("1", "true", "yes")
ORDER_QTY = int(os.getenv("ORDER_QTY", "1"))
PRODUCT_TYPE = os.getenv("PRODUCT_TYPE", "MIS")
MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

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
            return pd.DataFrame() # Return an empty DataFrame
        
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
        ws = client.open_by_by_key(sheet_id).worksheet(sheet_name)
        if isinstance(content, list):
            ws.update(values=content, range_name=cell)
        else:
            ws.update(values=[[content]], range_name=cell)
        logging.info(f"Sheet '{sheet_name}' updated at cell {cell}.")
    except Exception as e:
        logging.error(f"Sheet update failed for '{sheet_name}': {e}")

# ✅ नया फ़ंक्शन: Angel One API से ऐतिहासिक डेटा प्राप्त करने के लिए
def fetch_historical_data(api, symbol, token_info, days=10):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        params = {
            "exchange": token_info['exch_seg'],
            "symboltoken": token_info['token'],
            "interval": "ONE_DAY", # 1-दिन के अंतराल पर डेटा प्राप्त करें
            "fromdate": start_date.strftime("%Y-%m-%d %H:%M"),
            "todate": end_date.strftime("%Y-%m-%d %H:%M")
        }
        
        historical_data = api.getCandleData(params)
        
        if 'data' not in historical_data:
            logging.warning(f"No historical data found for {symbol}.")
            return pd.DataFrame()
        
        df_hist = pd.DataFrame(historical_data['data'], columns=["date", "open", "high", "low", "close", "volume"])
        df_hist['close'] = pd.to_numeric(df_hist['close'])
        
        logging.info(f"Successfully fetched {len(df_hist)} data points for {symbol}.")
        return df_hist
    except Exception as e:
        logging.error(f"Failed to fetch historical data for {symbol}: {e}")
        return pd.DataFrame()

def get_live_prices_and_update_sheet(api, symbols_df, gs_client, sheet_id, sheet_name):
    # ... (यह फ़ंक्शन अपरिवर्तित है) ...
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

def get_tokens_from_api():
    # ... (यह फ़ंक्शन अपरिवर्तित है) ...
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
        
        keep = df[
            ((df["exch_seg"] == "NFO") & (df["instrumenttype"] == "OPTIDX")) |
            ((df["exch_seg"] == "BSE") & (df["symbol"] == "SENSEX"))
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
        df['CLOSE'] = pd.to_numeric(df['CLOSE'], errors='coerce')
        df = df.dropna(subset=['SYMBOL', 'CLOSE'])
        
        if len(df) < 15:
            logging.warning("Not enough data to calculate indicators (min 15 required).")
            return pd.DataFrame()

        # MACD and RSI calculation
        delta = df['CLOSE'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        
        rs = np.where(loss == 0, np.inf, gain / loss)
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

def place_order(api, symbol, side, token_info, quantity, gs_client=None):
    if not api:
        logging.info(f"Dry-run: Would have placed a {side} order for {symbol} with quantity {quantity}.")
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

    df = read_google_sheet_data(gs_client, GSHEET_ID, SHEET_NAME)
    if df.empty:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "⚠️ Google Sheet empty or invalid")
        exit(1)

    df['symboltoken'] = df['SYMBOL'].apply(lambda s: tokens.get(s, {}).get('token'))
    df['exch_seg'] = df['SYMBOL'].apply(lambda s: tokens.get(s, {}).get('exch_seg'))
    df = df.dropna(subset=['SYMBOL', 'symboltoken', 'exch_seg'])

    if not df.empty:
        get_live_prices_and_update_sheet(angel_api, df, gs_client, GSHEET_ID, SHEET_NAME)
    
    df_updated = read_google_sheet_data(gs_client, GSHEET_ID, SHEET_NAME)
    if df_updated.empty:
        logging.error("Failed to re-read updated sheet data.")
        exit(1)
    
    # ✅ FIX: प्रत्येक प्रतीक के लिए ऐतिहासिक डेटा प्राप्त करें और उन्हें मर्ज करें
    full_df = pd.DataFrame()
    for symbol in df_updated['SYMBOL'].unique():
        token_info = tokens.get(symbol)
        if token_info:
            hist_df = fetch_historical_data(angel_api, symbol, token_info, days=15) # 15 दिन का डेटा लें
            if not hist_df.empty:
                # लाइव डेटा को ऐतिहासिक डेटा के साथ जोड़ें
                live_price_row = df_updated[df_updated['SYMBOL'] == symbol].copy()
                live_price_row = live_price_row.rename(columns={'CLOSE': 'close'})
                live_price_row['date'] = datetime.now()
                
                combined_df = pd.concat([hist_df, live_price_row[['date', 'close']]], ignore_index=True)
                combined_df['SYMBOL'] = symbol
                full_df = pd.concat([full_df, combined_df], ignore_index=True)

    if full_df.empty:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "❌ Failed to fetch historical data.")
        send_telegram_message("❌ Error: Failed to fetch historical data. Cannot calculate indicators.")
        exit(1)
    
    # संकेतक की गणना करें
    df_with_indicators = calculate_indicators(full_df)
    
    if df_with_indicators.empty:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "❌ Indicator calculation failed. Not enough data.")
        logging.error("Exiting due to failed indicator calculation.")
        send_telegram_message("❌ Error: Indicator calculation failed. Not enough data.")
        exit(1)
        
    signals = generate_signals(df_with_indicators)
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
                try:
                    quantity_from_sheet = df_updated[df_updated['SYMBOL'] == symbol]['QUANTITY'].iloc[0]
                    order_quantity = int(quantity_from_sheet)
                except (KeyError, IndexError, ValueError):
                    logging.warning(f"Quantity column not found or invalid for {symbol}. Using default quantity: {ORDER_QTY}")
                    order_quantity = ORDER_QTY
                
                place_order(angel_api, symbol, side, info, order_quantity, gs_client)
            else:
                logging.warning(f"Token not found for {symbol}.")
    else:
        update_google_sheet_cell(gs_client, GSHEET_ID, SHEET_NAME, "G2", "No signals generated.")
        send_telegram_message("ℹ️ No trading signals generated in this run.", gs_client)
    
    logging.info("Bot run completed.")
