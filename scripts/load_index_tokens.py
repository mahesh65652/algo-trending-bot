import pandas as pd
import os

def load_index_tokens(file_path="data/instruments.csv"):
    """
    AngelOne instruments.csv से Index tokens load करता है
    :param file_path: CSV file path
    :return: dict {Index: Token}
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Instruments file not found: {file_path}")

    df = pd.read_csv(file_path)

    # आपको जिन indices चाहिए
    index_names = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]

    tokens = {}
    for index in index_names:
        row = df[(df['name'] == index) & (df['exch_seg'] == "NSE")]
        if not row.empty:
            tokens[index] = str(row.iloc[0]['token'])
        else:
            tokens[index] = None

    return tokens


if __name__ == "__main__":
    try:
        tokens = load_index_tokens()
        print("✅ Loaded Index Tokens:", tokens)
    except Exception as e:
        print("❌ Error loading tokens:", e)
