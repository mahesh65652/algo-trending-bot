import json
from SmartApi.smartConnect import SmartConnect

# Step 1: Load credentials from credentials.json
with open("credentials.json") as f:
    creds = json.load(f)

api_key = creds["api_key"]
client_id = creds["client_id"]
password = creds["password"]
totp = creds["totp"]

# Step 2: Create SmartConnect object
obj = SmartConnect(api_key=api_key)

try:
    # Step 3: Login & generate session
    session = obj.generateSession(client_id, password, totp)

    # Step 4: Get tokens from session response
    feed_token = session["data"]["feedToken"]
    refresh_token = session["data"]["refreshToken"]

    print("Feed Token:", feed_token)
    print("Refresh Token:", refresh_token)

    # Step 5: Save tokens to token_output.json
    with open("token_output.json", "w") as outfile:
        json.dump({
            "feed_token": feed_token,
            "refresh_token": refresh_token
        }, outfile, indent=4)

except Exception as e:
    print("❌ Error generating tokens:", str(e))

