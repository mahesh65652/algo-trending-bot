from scripts.manual_atm import manual_atm

def get_atm_price(symbol, live_price):
    """
    ATM strike निकालो।
    अगर API fail हो गई तो manual ATM use करो।
    """
    if live_price is not None:
        # nearest 50 पर round
        return round(live_price / 50) * 50, False
    else:
        print(f"⚠️ API fail → using manual ATM for {symbol}")
        return manual_atm[symbol], True
