# 📈 Algo Trading Bot – Google Sheets + Angel One API

This bot reads trading signals from a Google Sheet and places orders using the Angel One SmartAPI.

---

## 📁 Files Structure

- `main.py` – Main script to coordinate reading signals and placing orders.
- `sheet_handler.py` – Handles reading/writing data to your Google Sheet.
- `angel_api.py` – Placeholder for Angel One order placement logic.
- `.env.example` – Example environment variables you need to set up.

---

## 🔧 How it Works

1. Google Sheet is updated with symbols and signal logic (Buy/Sell/Hold).
2. The bot reads values like RSI, EMA, Price, etc. from the sheet.
3. Based on logic, it generates a final signal.
4. It places live orders using Angel One API.

---

## 📄 Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
pip install -r requirements.txt
python main.py
(.env)

ANGEL_API_KEY

ANGEL_API_SECRET

CLIENT_CODE

TOTP

SHEET_ID 
