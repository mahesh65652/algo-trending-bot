import requests

# 🔐 अपनी API Key और क्लाइंट कोड यहाँ भरो
API_KEY = "10zzA50X"
CLIENT_CODE = "YOUR_CLIENT_CODE"
PASSWORD = "YOUR_PASSWORD"
TOTP = "123456"  # अगर आपके Angel One में TOTP ऑन है

url = "https://apiconnect.angelone.in/rest/auth/angelbroking/jwt/v1/generateTokens"

payload = {
    "clientcode": CLIENT_CODE,
    "password": PASSWORD,
    "totp": TOTP,
    "appsource": API_KEY
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 200:
    data = response.json()
    print("✅ JWT Token:", data.get("data", {}).get("jwtToken"))
    print("🔁 Refresh Token:", data.get("data", {}).get("refreshToken"))

    # Save to file
    with open("tokens.json", "w") as f:
        import json
        json.dump(data["data"], f, indent=2)
    print("💾 Tokens saved to tokens.json")

else:
    print("❌ Failed to generate token:", response.text)


import requests
import json
import pyotp

# ✅ अपनी जानकारी नीचे भरो
API_KEY = "10zzA50X"
CLIENT_CODE = "A123456"       # Angel One Client ID
PASSWORD = "YourPassword123"
TOTP_SECRET = "O5HWT7XOSIIRU44G2CCHZC3EDQ"  # Angel One TOTP Secret

# 🔁 TOTP Generate करो
totp = pyotp.TOTP(TOTP_SECRET).now()

# 🔗 Angel One Token URL
url = "https://apiconnect.angelone.in/rest/auth/angelbroking/jwt/v1/generateTokens"

# 📦 Request Payload
payload = {
    "clientcode": CLIENT_CODE,
    "password": PASSWORD,
    "totp": totp,
    "appsource": API_KEY
}

headers = {
    "Content-Type": "application/json"
}

# 🚀 Token Request भेजो
response = requests.post(url, json=payload, headers=headers)

# 📦 Response Process करो
if response.status_code == 200:
    data = response.json()
    jwt_token = data.get("data", {}).get("jwtToken")
    refresh_token = data.get("data", {}).get("refreshToken")

    print("✅ JWT Token:", jwt_token)
    print("🔁 Refresh Token:", refresh_token)

    # 💾 Token Save करो
    with open("tokens.json", "w") as f:
        json.dump(data["data"], f, indent=2)
    print("💾 Saved to tokens.json")

else:
    print("❌ Failed:", response.status_code, response.text)

