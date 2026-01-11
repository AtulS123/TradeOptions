from kiteconnect import KiteConnect
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("API_KEY", "5f814cggb2e7m8z9").strip()
token_file = "access_token.txt"

def debug():
    try:
        with open(token_file, "r") as f:
            access_token = f.read().strip()
            
        print(f"Using Token: {access_token[:6]}...")
        
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(access_token)
        
        print("Profile:", kite.profile().get("user_name"))
        
        print("Fetching Quote...")
        q = kite.quote(["NSE:NIFTY 50"])
        token = q["NSE:NIFTY 50"]["instrument_token"]
        print(f"Token: {token}")
        
        print("Fetching Historical Data (1 day, 2024)...")

        print("Fetching Historical Data (2024)...")
        s_date = datetime(2024, 1, 1, 9, 15)
        e_date = datetime(2024, 1, 2, 15, 30)

        
        records = kite.historical_data(token, s_date, e_date, "minute")
        print(f"Success! {len(records)} records.")
        
    except Exception as e:
        print(f"\nFAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug()
