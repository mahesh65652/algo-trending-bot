import pandas as pd
import os

def load_index_tokens(file_path="data/instruments.csv"):
    """
    Loads Index tokens from a CSV file, handling name discrepancies.
    :param file_path: CSV file path
    :return: dict {Index: Token}
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Instruments file not found: {file_path}")

    df = pd.read_csv(file_path)

    # A dictionary mapping your desired symbol to the possible names in the CSV.
    index_map = {
        "NIFTY": ["Nifty 50", "NIFTY"],
        "BANKNIFTY": ["Nifty Bank", "BANKNIFTY"],
        "FINNIFTY": ["Nifty Fin Service", "FINNIFTY"],
        "MIDCPNIFTY": ["NIFTY MIDCAP 100", "MIDCPNIFTY"],
        "SENSEX": ["SENSEX"],
    }

    tokens = {}
    for short_name, possible_names in index_map.items():
        # Find the row where 'name' OR 'symbol' matches a possible name
        row = df[(df['name'].isin(possible_names)) | (df['symbol'].isin(possible_names)) & (df['exch_seg'].isin(["NSE", "BSE"]))]
        
        if not row.empty:
            tokens[short_name] = str(row.iloc[0]['token'])
        else:
            tokens[short_name] = None
            
    return tokens

if __name__ == "__main__":
    try:
        # Assuming your instruments.csv is in a 'data' folder
        tokens = load_index_tokens(file_path="data/instruments.csv")
        print("✅ Loaded Index Tokens:", tokens)
    except Exception as e:
        print("❌ Error loading tokens:", e)
