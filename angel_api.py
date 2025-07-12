Angel One API integration code goes here
from smartapi import SmartConnect
import os

def place_order(symbol, action):
    print(f"Placing {action} order for {symbol}")

    obj = SmartConnect(api_key=os.environ['ANGEL_API_KEY'])
    data = obj.generateSession(os.environ['ANGEL_CLIENT_ID'], os.environ['ANGEL_PIN'])

    order_params = {
        "variety": "NORMAL",
        "tradingsymbol": symbol,
        "symboltoken": "99926009",  # आपको लाइव डेटा से लेना होगा
        "transactiontype": action.upper(),  # "BUY" or "SELL"
        "exchange": "NSE",
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "price": 0,
        "squareoff": "0",
        "stoploss": "0",
        "quantity": 1
    }

    try:
        response = obj.placeOrder(order_params)
        print("✅ Order placed:", response)
    except Exception as e:
        print("❌ Error placing order:", e)
