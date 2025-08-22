import os
import json
import time
import math
from datetime import datetime, timedelta

import requests
import pandas as pd
import pyotp

# Try import SmartConnect from both package names
try:
    from SmartApi import SmartConnect
except ImportError:
    try:
        from smartapi import SmartConnect
    except ImportError:
        SmartConnect = None  # Will be handled with an error message later

# gspread/oauth helper
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    from gspread.exceptions import APIError, WorksheetNotFound
except ImportError:
    gspread = None

# ---------- CONFIG (environment variable names) ----------
GSHEET_CREDS_ENV = "GSHEET_CREDS_JSON"
GSHEET_ID_ENV = "GSHEET_ID"
ANGEL_API_KEY_ENV = "ANGEL_API_KEY"
ANGEL_CLIENT_CODE_ENV = "ANGEL_CLIENT_CODE"
ANGEL_CLIENT_PWD_ENV = "ANGEL_CLIENT_PWD"
ANGEL_TOTP_SECRET_ENV = "ANGEL_TOTP_SECRET"
TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ENV = "TELEGRAM_CHAT_ID"

MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
DATA_DIR = "data"
MASTER_CACHE = os.path.join(DATA_DIR, "master.json")

# ---------- Telegram ----------
def send_telegram_message(text: str):
    token = os.getenv(TELEGRAM_TOKEN_ENV)
    chat_id = os.getenv(TELEGRAM_CHAT_ENV)
    if not token or not chat_id:
        print("⚠️ Telegram credentials missing; skipping send.")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=6,
        )
        if resp.status_code != 200:
            print("⚠ Telegram API returned", resp.status_code, resp.text)
    except Exception as e:
        print("⚠ Telegram send error:", e)

# ---------- Google Sheets helpers ----------
def gs_auth_from_env():
    if gspread is None:
        raise Exception("gspread/oauth2client not installed.")
    raw = os.getenv(GSHEET_CREDS_ENV)
    if not raw:
        raise Exception(f"❌ {GSHEET_CREDS_ENV} missing in env")
    try:
        creds_dict = json.loads(raw)
    except Exception as e:
        raise Exception(f"❌ GSHEET_CREDS_JSON invalid JSON: {e}")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def open_sheet(client, sheet_id):
    for attempt in range(4):
        try:
            ss = client.open_by_key(sheet_id)
            return ss
        except APIError as e:
            print("Google Sheets APIError:", e)
            time.sleep(2 + attempt * 2)
    raise Exception("❌ Failed to open Google Sheet.")

def read_sheet_values(ss, sheet_name):
    try:
        ws = ss.worksheet(sheet_name)
        return ws.get_all_values()
    except WorksheetNotFound:
        raise
    except Exception as e:
        print("❌ Error reading sheet:", e)
        return []

def ensure_trade_log_sheet(ss, name="TRADE_LOG"):
    try:
        ws = ss.worksheet(name)
    except WorksheetNotFound:
        ws = ss.add_worksheet(title=name, rows="1000", cols="20")
        headers = ["id", "symbol", "side", "entry_price", "sl", "tp", "status", "open_time", "close_time", "close_price", "notes"]
        ws.append_row(headers)
    return ss.worksheet(name)

def append_trade_log(ws, row_values):
    ws.append_row(row_values)

def update_trade_row(ws, row_index, updated_values: dict):
    headers = ws.row_values(1)
    for col_name, val in updated_values.items():
        if col_name in headers:
            col_idx = headers.index(col_name) + 1
            ws.update_cell(row_index, col_idx, val)

# ---------- Instruments master helpers ----------
def download_master_json():
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        r = requests.get(MASTER_URL, timeout=30)
        r.raise_for_status()
        data = r.json()
        with open(MASTER_CACHE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception as e:
        print("❌ Failed to download master JSON:", e)
        if os.path.exists(MASTER_CACHE):
            try:
                with open(MASTER_CACHE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

def build_token_map(master_json):
    m = {}
    if not master_json:
        return m
    for item in master_json:
        exch = (item.get("exch_seg") or "").upper()
        sym_candidates = []
        if item.get("tokensymbol"):
            sym_candidates.append(item.get("tokensymbol"))
        if item.get("symbol"):
            sym_candidates.append(item.get("symbol"))
        if item.get("name"):
            sym_candidates.append(item.get("name"))
        tok = item.get("token")
        for s in sym_candidates:
            if s:
                m[(exch, s.upper())] = tok
    return m

def lookup_token(token_map, exch, trading_symbol):
    return token_map.get((exch.upper(), trading_symbol.upper()))

# ---------- Indicators ----------
def ensure_numeric_series(series):
    return pd.to_numeric(series, errors="coerce")

def calculate_basic_indicators_from_values(values_table):
    if not values_table or len(values_table) < 2:
        return pd.DataFrame()
    headers = [h.strip() for h in values_table[0]]
    df = pd.DataFrame(values_table[1:], columns=headers)
    rename_map = {}
    for c in df.columns:
        if c.lower() == "close":
            rename_map[c] = "Close"
        elif c.lower() == "open":
            rename_map[c] = "Open"
        elif c.lower() == "high":
            rename_map[c] = "High"
        elif c.lower() == "low":
            rename_map[c] = "Low"
        elif c.lower() in ("symbol", "symbolname", "name"):
            rename_map[c] = "Symbol"
    if rename_map:
        df = df.rename(columns=rename_map)
    if "Close" not in df.columns:
        print("⚠️ 'Close' column missing in sheet; indicators can't be computed.")
        return pd.DataFrame()
    for col in ["Open", "High", "Low", "Close"]:
        if col in df.columns:
            df[col] = ensure_numeric_series(df[col])
    
    # Calculate indicators
    df["SMA_14"] = df["Close"].rolling(window=14, min_periods=1).mean()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / loss.replace(0, pd.NA)
    df["RSI_14"] = 100 - (100 / (1 + rs))
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    
    return df

# ---------- Signals ----------
def generate_index_signals(df):
    signals = []
    if df.empty or "SMA_14" not in df.columns:
        return signals
    if "Symbol" in df.columns:
        grouped = df.groupby("Symbol")
        for sym, g in grouped:
            last = g.iloc[-1]
            if pd.isna(last["Close"]) or pd.isna(last["SMA_14"]):
                continue
            if last["Close"] > last["SMA_14"]:
                signals.append(f"BUY {sym}")
            elif last["Close"] < last["SMA_14"]:
                signals.append(f"SELL {sym}")
    else:
        last = df.iloc[-1]
        sym = last.get("Symbol", "SYMBOL")
        if last["Close"] > last["SMA_14"]:
            signals.append(f"BUY {sym}")
        elif last["Close"] < last["SMA_14"]:
            signals.append(f"SELL {sym}")
    return signals

def generate_options_signals(df):
    signals = []
    if df.empty or "Symbol" not in df.columns:
        return signals
    grouped = df.groupby("Symbol")
    for sym, g in grouped:
        if len(g) < 2:
            continue
        last = g.iloc[-1]
        prev = g.iloc[-2]
        try:
            close = float(last["Close"])
            prev_high = float(prev.get("High", math.nan))
            prev_low = float(prev.get("Low", math.nan))
        except Exception:
            continue
        if close > prev_high:
            signals.append(f"BUY {sym}")
        elif close < prev_low:
            signals.append(f"SELL {sym}")
    return signals

# ---------- Main Execution ----------
if __name__ == "__main__":
    print("--- Starting Angel One Bot ---")
    
    # 1. Authenticate with Google Sheets
    try:
        gs_client = gs_auth_from_env()
        gs_sheet = open_sheet(gs_client, os.getenv(GSHEET_ID_ENV))
        trade_log_sheet = ensure_trade_log_sheet(gs_sheet)
    except Exception as e:
        print(f"❌ Google Sheets setup failed: {e}")
        send_telegram_message(f"🚨 Google Sheets Error: {e}")
        exit(1)
        
    # 2. Authenticate with Angel One
    if SmartConnect is None:
        print("❌ SmartApi library not installed. Exiting.")
        send_telegram_message("🚨 SmartApi library not installed. Exiting.")
        exit(1)
    
    try:
        smart = SmartConnect(api_key=os.getenv(ANGEL_API_KEY_ENV))
        # Use TOTP for session generation, which is more secure
        session_data = smart.generateSession(
            os.getenv(ANGEL_CLIENT_CODE_ENV),
            os.getenv(ANGEL_CLIENT_PWD_ENV),
            pyotp.TOTP(os.getenv(ANGEL_TOTP_SECRET_ENV)).now()
        )
        if 'data' not in session_data:
            raise Exception("Session data not returned.")
        print("✅ Angel One session generated successfully.")
    except Exception as e:
        print(f"❌ Angel One login failed: {e}")
        send_telegram_message(f"🚨 Angel One Login Failed: {e}")
        exit(1)
        
    # 3. Get Instruments Master Data
    token_map = build_token_map(download_master_json())
    if not token_map:
        print("❌ Failed to get master instrument data.")
        send_telegram_message("🚨 Failed to get master instrument data.")
        exit(1)
        
    # 4. Read data from Google Sheet (if any)
    try:
        index_data = read_sheet_values(gs_sheet, "INDEX_DATA")
        options_data = read_sheet_values(gs_sheet, "OPTIONS_DATA")
    except WorksheetNotFound:
        print("⚠️ Required worksheets not found. Skipping signal generation.")
        index_data = []
        options_data = []
        
    # 5. Calculate indicators and generate signals
    index_df = calculate_basic_indicators_from_values(index_data)
    options_df = calculate_basic_indicators_from_values(options_data)
    
    index_signals = generate_index_signals(index_df)
    options_signals = generate_options_signals(options_df)
    
    # 6. Send signals to Telegram
    if index_signals:
        signal_text = "🟢 **INDEX SIGNALS**\n" + "\n".join(index_signals)
        send_telegram_message(signal_text)
    
    if options_signals:
        signal_text = "✨ **OPTIONS SIGNALS**\n" + "\n".join(options_signals)
        send_telegram_message(signal_text)
        
    print("--- Bot execution complete ---")
