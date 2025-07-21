auto_token_save.py

import os
import pyotp
import json
from SmartApi.smartConnect import SmartConnect

# ✅ Load Env or Direct Config
api_key = os.getenv("ANGEL_API_KEY") or "अपना_API_KEY"
client_code = os.getenv("CLIENT_CODE") or "अपना_CLIENT_CODE"
api_secret = os.getenv("ANGEL_API_SECRET") or "अपना_API_SECRET"
totp_key = os.getenv("TOTP") or "अपना_TOTP_SECRET_KEY"

# ✅ Generate TOTP
totp = pyotp.TOTP(totp_key).now()

# ✅ Angel One Login
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(client_code, totp, api_secret)

if "access_token" in data:
    access_token = data["access_token"]
    refresh_token = data["refreshToken"]
    feed_token = obj.getfeedToken()

    # ✅ Save to .env format
    with open("token.env", "w") as f:
        f.write(f'ACCESS_TOKEN="{access_token}"\n')
        f.write(f'FEED_TOKEN="{feed_token}"\n')
        f.write(f'REFRESH_TOKEN="{refresh_token}"\n')

    print("✅ Tokens saved in token.env file")
else:
    print("❌ Login Failed:", data)
