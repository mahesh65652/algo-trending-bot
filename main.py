from sheet_handler import get_signals
from angel_api import place_order

def run():
    signals = get_signals()
    for signal in signals:
        symbol = signal["symbol"]
        action = signal["action"]
        if action in ["BUY", "SELL"]:
            place_order(symbol, action)

if __name__ == "__main__":
    run()
