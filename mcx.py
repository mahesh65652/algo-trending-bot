
from utils.sheet import get_symbols, update_sheet_signals
from utils.ltp import fetch_ltp
from utils.telegram import send_telegram_message

def format_signal(symbol, ltp, decision="HOLD"):
    try:
        ltp = float(ltp)
        price_str = f"₹{round(ltp)}" if ltp > 0 else "₹ERR"
        return f"{symbol} : {decision} @ {price_str}"
    except:
        return f"{symbol} : {decision} @ ₹ERR"

def main():
    symbols = get_symbols()
    results = []

    for item in symbols:
        sym = item.get("symbol")
        token = item.get("token")
        exch = item.get("exchange")

        # 🔐 Check only MCX Option Contracts
        if exch != "MCX":
            continue
        if not sym.endswith("CE") and not sym.endswith("PE"):
            continue  # skip FUTURE contracts

        # 🔍 LTP fetch
        ltp = fetch_ltp(sym, token, exch)
        signal = "HOLD"
        if ltp:
            if ltp > item.get("buy_above", 0):
                signal = "BUY"
            elif ltp < item.get("sell_below", 0):
                signal = "SELL"

        results.append({"symbol": sym, "ltp": ltp, "signal": signal})
        msg = format_signal(sym, ltp, signal)
        send_telegram_message(msg)

    update_sheet_signals(results)
    print("✅ Commodity Options script done.")

if __name__ == "__main__":
    main()
