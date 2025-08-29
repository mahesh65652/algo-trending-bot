#!/usr/bin/env python3
import requests
import json
import logging
import sys
import pandas as pd
from pathlib import Path
import os
import re

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

        # Define the indices we are interested in.
        # Use a regex pattern to match variations of names.
        indices_pattern = r'^(NIFTY|BANKNIFTY|FINNIFTY|MIDCPNIFTY|SENSEX|NIFTY 50|NIFTY BANK|NIFTY FINANCIAL SERVICES|NIFTY MIDCAP 100)'

        # Filter for F&O instruments and the specified indices.
        filtered_df = df[
            (df['exch_seg'] == 'NFO') |
            (df['exch_seg'] == 'BSE') | # Include BSE for SENSEX
            (df['exch_seg'] == 'NSE') & df['name'].str.contains(indices_pattern, regex=True)
        ].copy()

        if filtered_df.empty:
            logging.error("❌ Filtered dataframe is empty. No tokens found.")
            return

        # Create a dictionary with simplified symbols for easier lookup.
        simplified_tokens = {}
        for _, row in filtered_df.iterrows():
            if re.search(r'NIFTY 50', row['name']):
                simplified_tokens['NIFTY'] = row.to_dict()
            elif re.search(r'NIFTY BANK', row['name']):
                simplified_tokens['BANKNIFTY'] = row.to_dict()
            elif re.search(r'NIFTY FINANCIAL SERVICES', row['name']):
                simplified_tokens['FINNIFTY'] = row.to_dict()
            elif re.search(r'NIFTY MIDCAP 100', row['name']):
                simplified_tokens['MIDCPNIFTY'] = row.to_dict()
            elif re.search(r'SENSEX', row['name']):
                simplified_tokens['SENSEX'] = row.to_dict()
            # Add any other relevant token directly if not an index
            elif row['exch_seg'] == 'NFO':
                simplified_tokens[row['symbol']] = row.to_dict()
                
        # Handle cases where the symbol is a better identifier (e.g., in F&O)
        final_tokens = {v['symbol']: v for v in simplified_tokens.values()}
        
        with open('tokens.json', 'w') as f:
            json.dump(final_tokens, f, indent=4)
        
        logging.info("✅ Tokens successfully saved to tokens.json")
        logging.info(f"Saved {len(final_tokens)} tokens.")

    except Exception as e:
        logging.error(f"❌ Error fetching or saving tokens: {e}")

if __name__ == "__main__":
    fetch_and_save_tokens()
