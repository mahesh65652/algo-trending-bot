
# main.py
import os
import json
import time
import math
from datetime import datetime, timedelta

import requests
import pandas as pd
import pyotp

# try import SmartConnect from both package names
try:
    from SmartApi import SmartConnect
except Exception:
    try:
        from smartapi import SmartConnect
    except Exception:
        SmartConnect = None  # will error later

# gspread/oauth helper
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    from gspread.exceptions import APIError, WorksheetNotFound
except Exception:
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
        raise Exception(f"{GSHEET_CREDS_ENV} missing in env")
    try:
        creds_dict = json.loads(raw)
    except Exception as e:
        raise Exception(f"GSHEET_CREDS_JSON invalid JSON: {e}")
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
    raise Exception("Failed to open Google Sheet.")

def read_sheet_values(ss, sheet_name):
    try:
        ws = ss.worksheet(sheet_name)
        return ws.get_all_values()
    except WorksheetNotFound:
        raise
    except Exception as e:
        print("Error reading sheet:", e)
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

def find_open_trades(ws):
    records = ws.get_all_records()
    open_rows = []
    for idx, r in enumerate(records, start=2):
        if str(r.get("status", "")).upper() == "OPEN":
            open_rows.append((idx, r))
    return open_rows

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
        # try load cached
        if os.path.exists(MASTER_CACHE):
            try:
                with open(MASTER_CACHE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

def build_token_map(master_json):
    m = {}
    for item in master_json:
        exch = (item.get("exch_seg") or "").upper()
        # prefer tokensymbol / symbol / name
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

# ---------- Trade helpers ----------
def calculate_sl_tp(entry_price: float, side: str):
    if side.upper() == "BUY":
        sl = round(entry_price * (1 - 0.03), 4)
        tp = round(entry_price * (1 + 0.10), 4)
    else:
        sl = round(entry_price * (1 + 0.03), 4)
        tp = round(entry_price * (1 - 0.10), 4)
    return sl, tp

def open_trade_in_sheet(ws_trade, symbol, side, entry_price, notes=""):
    entry_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    sl, tp = calculate_sl_tp(entry_price, side)
    tid = int(time.time())
    row = [tid, symbol, side, entry_price, sl, tp, "OPEN", entry_time, "", "", notes]
    append_trade_log(ws_trade, row)
    send_telegram_message(f"✅ OPEN {side} {symbol} @ {entry_price} SL={sl} TP={tp}")

def manage_open_trades_with_sheet(ws_trade, token_map, api_instance):
    records = ws_trade.get_all_records()
    for idx, rec in enumerate(records, start=2):
        status = str(rec.get("status", "")).upper()
        if status != "OPEN":
            continue
        symbol = rec.get("symbol")
        side = rec.get("side")
        entry_price = rec.get("entry_price")
        sl = rec.get("sl")
        tp = rec.get("tp")
        if not symbol:
            continue
        token = None
        for exch in ("NFO", "NSE", "MCX", "BSE"):
            token = lookup_token(token_map, exch, symbol)
            if token:
                exch_used = exch
                break
        if not token:
            print(f"⚠ Token not found for open trade {symbol}; skipping price check.")
            continue
        try:
            ltp_data = api_instance.ltpData(exch_used, symbol, token)
            ltp = None
            if ltp_data and isinstance(ltp_data, dict) and ltp_data.get("data"):
                ltp = ltp_data["data"].get("ltp")
            if not ltp:
                print(f"⚠ No LTP for {symbol}")
                continue
            price = float(ltp)
        except Exception as e:
            print("⚠ Error fetching ltp for", symbol, e)
            continue
        closed_reason = None
        if side.upper() == "BUY":
            if price <= float(sl):
                closed_reason = "SL"
            elif price >= float(tp):
                closed_reason = "TP"
        else:
            if price >= float(sl):
                closed_reason = "SL"
            elif price <= float(tp):
                closed_reason = "TP"
        if closed_reason:
            close_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            updates = {
                "status": "CLOSED",
                "close_time": close_time,
                "close_price": price,
                "notes": f"Closed by {closed_reason}"
            }
            update_trade_row(ws_trade, idx, updates)
            send_telegram_message(f"🔒 {symbol} {closed_reason} at {price} (entry {entry_price})")
            print(f"Closed trade {symbol} reason {closed_reason} at {price}")

# ---------- Main ----------
def main():
    # 1) google auth
    try:
        client = gs_auth_from_env()
    except Exception as e:
        print("❌ Google Sheets auth error:", e)
        return
    sheet_id = os.getenv(GSHEET_ID_ENV)
    if not sheet_id:
        print(f"❌ {GSHEET_ID_ENV} missing in env")
        return
    ss = open_sheet(client, sheet_id)
    try:
        summary_ws = ss.sheet1
    except Exception:
        summary_ws = ss.add_worksheet(title="Summary", rows="1000", cols="20")
    # 2) smartapi login
    api_key = os.getenv(ANGEL_API_KEY_ENV)
    client_code = os.getenv(ANGEL_CLIENT_CODE_ENV)
    pwd = os.getenv(ANGEL_CLIENT_PWD_ENV)
    totp_secret = os.getenv(ANGEL_TOTP_SECRET_ENV)
    if not SmartConnect:
        print("❌ SmartConnect library missing. Install smartapi-python or SmartApi package.")
        return
    if not all([api_key, client_code, pwd, totp_secret]):
        print("❌ Angel One credentials missing in env.")
        return
    api = SmartConnect(api_key)
    try:
        otp = pyotp.TOTP(totp_secret.strip()).now()
        print("🔑 Generated OTP:", otp)
        data = api.generateSession(client_code, pwd, otp)
        if not data or not data.get("status"):
            print("❌ Login failed:", data)
            return
        print("✅ Angel One login successful.")
    except Exception as e:
        print("❌ Angel login exception:", e)
        return
    # 3) master file
    master = download_master_json()
    token_map = build_token_map(master) if master else {}
    # 4) read LIVE DATA
    try:
        values = read_sheet_values(ss, "LIVE DATA")
    except WorksheetNotFound:
        print("⚠ LIVE DATA sheet not found. Create sheet named 'LIVE DATA' with data.")
        return
    except Exception as e:
        print("Error reading LIVE DATA:", e)
        return
    df = calculate_basic_indicators_from_values(values)
    if df.empty:
        print("⚠ Indicators not computed; exiting.")
        return
    # 5) signals
    index_signals = generate_index_signals(df)
    options_signals = generate_options_signals(df)
    all_signals = index_signals + options_signals
    try:
        if all_signals:
            summary_ws.update("J1", [["Signals"]])
            summary_ws.update("J2", [[s] for s in all_signals])
        else:
            summary_ws.update("J1", [["Signals"]])
            summary_ws.update("J2", [["(no signals)"]])
    except Exception as e:
        print("⚠ Could not update signals to sheet:", e)
    # 6) trades
    ws_trade = ensure_trade_log_sheet(ss, "TRADE_LOG")
    for sig in all_signals:
        try:
            parts = sig.split()
            side = parts[0]
            symbol = parts[1]
            # get price
            price = None
            if "Symbol" in df.columns:
                g = df[df["Symbol"].astype(str).str.upper() == symbol.upper()]
                if not g.empty:
                    price = float(g["Close"].iloc[-1])
            if price is None:
                token = lookup_token(token_map, "NSE", symbol) or lookup_token(token_map, "NFO", symbol) or lookup_token(token_map, "MCX", symbol)
                if token:
                    d = api.ltpData("NSE", symbol, token)
                    if d and d.get("data"):
                        price = float(d["data"].get("ltp"))
            if price is None:
                print("⚠ Price not found for", symbol, "; skipping open trade.")
                continue
            open_trade_in_sheet(ws_trade, symbol, side, price, notes="signal_opened")
        except Exception as e:
            print("⚠ error opening trade for signal", sig, e)
    # 7) manage open trades
    try:
        manage_open_trades_with_sheet(ws_trade, token_map, api)
    except Exception as e:
        print("⚠ manage trades error:", e)
    # 8) ATM summary + telegram
    indices_to_try = [
        {"name": "NIFTY", "step": 50, "exch": "NSE"},
        {"name": "BANKNIFTY", "step": 100, "exch": "NSE"},
        {"name": "FINNIFTY", "step": 50, "exch": "NSE"},
        {"name": "MIDCPNIFTY", "step": 100, "exch": "NSE"},
        {"name": "SENSEX", "step": 100, "exch": "BSE"},
    ]
    lines = ["✅ ATM Options Algo Run"]
    for idx in indices_to_try:
        try:
            symbol = idx["name"]
            if "Symbol" in df.columns and symbol in df["Symbol"].values:
                spot = float(df[df["Symbol"] == symbol]["Close"].iloc[-1])
            else:
                token = lookup_token(token_map, idx["exch"], symbol)
                if token:
                    ltp_data = api.ltpData(idx["exch"], symbol, token)
                    spot = float(ltp_data["data"]["ltp"]) if ltp_data and ltp_data.get("data") else None
                else:
                    spot = None
            if spot is None:
                lines.append(f"{symbol} Error: token/spot not found")
                continue
            step = idx["step"]
            atm = round(spot / step) * step
            ce_sym = f"{symbol}{atm}CE"
            pe_sym = f"{symbol}{atm}PE"
            ce_token = lookup_token(token_map, "NFO", ce_sym)
            pe_token = lookup_token(token_map, "NFO", pe_sym)
            ce_ltp = "(no-data)"
            pe_ltp = "(no-data)"
            if ce_token:
                d = api.ltpData("NFO", ce_sym, ce_token)
                if d and d.get("data"):
                    ce_ltp = d["data"].get("ltp")
            if pe_token:
                d = api.ltpData("NFO", pe_sym, pe_token)
                if d and d.get("data"):
                    pe_ltp = d["data"].get("ltp")
            lines.append(f"{symbol} Spot:{spot} Strike:{atm} CE:{ce_ltp} PE:{pe_ltp}")
        except Exception as e:
            lines.append(f"{symbol} Error: {e}")
    try:
        summary_ws.update("A1", [["Index Summary"]])
        summary_ws.update("A2", [[l] for l in lines[1:]])
    except Exception:
        pass
    send_telegram_message("\n".join(lines))
    print("✅ Run completed.")

if __name__ == "__main__":
    main()
