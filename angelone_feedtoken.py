import json
from SmartApi.smartConnect import SmartConnect

# Load credentials from JSON file
with open("credentials.json") as f:
    creds = json.load(f)

api_key = creds["api_key"]
client_id = creds["client_id"]
password = creds["password"]
totp = creds["totp"]

# Create SmartConnect object
obj = SmartConnect(api_key=api_key)

try:
    # Login
    data = obj.generateSession(client_id, password, totp)

    # Get tokens
    refreshToken = data["data"]["refreshToken"]
    feedToken = obj.getfeedToken()

    # Print tokens
    print("Feed Token:", feedToken)
    print("Refresh Token:", refreshToken)

    # Save to JSON
    with open("token_output.json", "w") as outfile:
        json.dump({
            "feed_token": feedToken,
            "refresh_token": refreshToken
        }, outfile, indent=4)

except Exception as e:
    print("Error:", str(e))

import json
from SmartApi.smartConnect import SmartConnect

with open("credentials.json") as f:
    creds = json.load(f)

api_key = creds["api_key"]
client_id = creds["client_id"]
password = creds["password"]
totp = creds["totp"]

obj = SmartConnect(api_key=api_key)

try:
    data = obj.generateSession(client_id, password, totp)
    refreshToken = data["data"]["refreshToken"]
    feedToken = obj.getfeedToken()

    print("Feed Token:", feedToken)
    print("Refresh Token:", refreshToken)

    with open("token_output.json", "w") as outfile:
        json.dump({
            "feed_token": feedToken,
            "refresh_token": refreshToken
        }, outfile, indent=4)

except Exception as e:
    print("Error:", str(e))

import json
from SmartApi.smartConnect import SmartConnect

# Load credentials from JSON file
with open("credentials.json") as f:
    creds = json.load(f)

api_key = creds["api_key"]
client_id = creds["client_id"]
password = creds["password"]
totp = creds["totp"]

obj = SmartConnect(api_key=api_key)

try:
    # Login
    data = obj.generateSession(client_id, password, totp)

    # Tokens from response
    feedToken = data["data"]["feedToken"]
    refreshToken = data["data"]["refreshToken"]

    print("Feed Token:", feedToken)
    print("Refresh Token:", refreshToken)

    # Save tokens
    with open("token_output.json", "w") as outfile:
        json.dump({
            "feed_token": feedToken,
            "refresh_token": refreshToken
        }, outfile, indent=4)

except Exception as e:
    print("Error:", str(e))
