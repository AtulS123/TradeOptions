import logging
import json
from kiteconnect import KiteConnect

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Credentials 
API_KEY = "5f814cggb2e7m8z9"
API_SECRET = "l7tc02thzpmeack5ge4xbwl3dboalz4m"
# REQUEST_TOKEN will be updated manually or replaced here
REQUEST_TOKEN = "lQRTukggwHivyeA34WOiBKibXAWjA5u0" 

def test_connection():
    print(f"Initializing KiteConnect with API_KEY: {API_KEY}")
    try:
        kite = KiteConnect(api_key=API_KEY)

        print(f"Generating session with REQUEST_TOKEN: {REQUEST_TOKEN}")
        data = kite.generate_session(REQUEST_TOKEN, api_secret=API_SECRET)
        
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        
        print("-" * 50)
        print(f"SUCCESS! Access Token: {access_token}")
        print("-" * 50)
        
        # Save token to file
        with open("access_token.txt", "w") as f:
            f.write(access_token)
        print("Access token saved to 'access_token.txt'")

        # Test fetch LTP for NIFTY 50
        instrument = "NSE:NIFTY 50"
        print(f"Fetching LTP for {instrument}...")
        ltp = kite.ltp(instrument)
        
        if instrument in ltp:
            print(f"Connection Successful! Nifty is at: {ltp[instrument]['last_price']}")
        else:
            print(f"Failed to fetch LTP for {instrument}. Response: {ltp}")

    except Exception as e:
        print("\nERROR FAILED TO CONNECT:")
        print(e)

if __name__ == "__main__":
    test_connection()
