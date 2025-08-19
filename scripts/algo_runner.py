from scripts.utils import get_atm_price

def run_algo(symbol, live_price, signal):
    """
    Safe trading logic:
    - अगर API सही है → trade execute होगा।
    - अगर API fail है → सिर्फ trend दिखेगा (no trade)।
    """
    atm_strike, api_failed = get_atm_price(symbol, live_price)

    if api_failed:
        msg = f"{symbol} → ATM {atm_strike} | Signal: {signal} | 🚫 No Trade (API FAIL)"
        log_to_sheet(symbol, atm_strike, msg)
        notify(msg)
    else:
        msg = f"{symbol} → ATM {atm_strike} | Signal: {signal} | ✅ Trade Executed"
        log_to_sheet(symbol, atm_strike, msg)
        place_trade(symbol, atm_strike, signal)
        notify(msg)


# Dummy placeholders (replace with your sheet / telegram / broker code)
def log_to_sheet(symbol, strike, msg):
    print("Sheet Update:", msg)

def notify(msg):
    print("Telegram:", msg)

def place_trade(symbol, strike, signal):
    print("Placed", signal, "for", symbol, "ATM", strike)


if __name__ == "__main__":
    # Example run
    run_algo("NIFTY", None, "BUY")       # API fail → सिर्फ trend
    run_algo("BANKNIFTY", 50025, "SELL") # API ok → trade
