import pyotp
from smartapi import SmartConnect
import os
from dotenv import load_dotenv

load_dotenv()

client_code = os.getenv("CLIENT_CODE")
api_key = os.getenv("API_KEY")
password = os.getenv("PASSWORD")
totp_secret = os.getenv("TOTP_SECRET")
pin = os.getenv("PIN")

# Generate TOTP
totp = pyotp.TOTP(totp_secret).now()

# Create SmartConnect object
obj = SmartConnect(api_key=api_key)

try:
    data = obj.generateSession(client_code, password, totp)
    refreshToken = data['data']['refreshToken']
    
    # Fetch Profile
    profile = obj.getProfile(refreshToken)
    print("✅ Login Successful!")
    print("Client Code:", profile['data']['clientcode'])
    
    # Save token if needed
    with open("token.txt", "w") as f:
        f.write(str(data))
        
except Exception as e:
    print("❌ Login Failed:", e)
