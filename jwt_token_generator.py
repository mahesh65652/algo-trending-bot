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
