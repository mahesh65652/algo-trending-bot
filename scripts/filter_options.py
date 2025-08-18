import pandas as pd

# Input: Angel master contract (23MB वाला)
master_file = "data/tokens.csv"
# Output: छोटा CSV सिर्फ options के लिए
output_file = "data/options_tokens.csv"

symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]

def filter_options():
    # Load master CSV
    df = pd.read_csv(master_file)

    # Filter सिर्फ options
    options_df = df[
        (df["exch_seg"] == "NSE") &
        (df["instrumenttype"] == "OPTIDX") &
        (df["name"].isin(symbols))
    ]

    # Useful columns चुनें
    options_df = options_df[
        ["name", "tokensymbol", "expiry", "strike", "instrumenttype", "lotsize"]
    ]

    # Rename
    options_df.rename(columns={
        "name": "symbol",
        "tokensymbol": "token",
        "instrumenttype": "option_type"
    }, inplace=True)

    # Save
    options_df.to_csv(output_file, index=False)
    print(f"✅ Filtered options saved to {output_file} (rows: {len(options_df)})")

if __name__ == "__main__":
    filter_options()
