#!/usr/bin/env python3
import requests
import json
import logging
import sys
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

def fetch_and_save_tokens():
    """
    Fetches the master scrip data from Angel One API and saves a filtered version
    of NFO and NSE indices tokens to a local JSON file.
    """
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
            return

        df = pd.DataFrame(records)
        df["symbol"] = df["symbol"].str.upper()
        df["name"] = df["name"].str.upper()

        # Filter for NIFTY, BANKNIFTY, and other relevant instruments
        filtered_df = df[
            (df['exch_seg'] == 'NFO') |  # F&O scripts
            (df['name'].isin(['NIFTY 50', 'NIFTY BANK', 'NIFTY FINANCIAL SERVICES', 'NIFTY MIDCAP 100', 'SENSEX'])) # Common indices
        ].copy()

        if filtered_df.empty:
            logging.error("❌ Filtered dataframe is empty. No tokens found.")
            return

        tokens_dict = filtered_df.set_index("symbol").to_dict("records")
        
        with open('tokens.json', 'w') as f:
            json.dump(tokens_dict, f, indent=4)
        
        logging.info("✅ Tokens successfully saved to tokens.json")
        logging.info(f"Saved {len(tokens_dict)} tokens.")

    except Exception as e:
        logging.error(f"❌ Error fetching or saving tokens: {e}")

if __name__ == "__main__":
    fetch_and_save_tokens()
