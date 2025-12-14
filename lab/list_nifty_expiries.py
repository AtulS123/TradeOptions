import os
import sys
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from kiteconnect import KiteConnect

# Load .env
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

if not API_KEY:
    print("No credentials found")
    sys.exit(1)

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

instruments = kite.instruments("NFO")
df = pd.DataFrame(instruments)

print(f"Total Instruments: {len(df)}")
nifty_rows = df[df['name'] == 'NIFTY']
print(f"NIFTY Rows: {len(nifty_rows)}")

if not nifty_rows.empty:
    nifty_rows['expiry'] = pd.to_datetime(nifty_rows['expiry']).dt.date
    expiries = sorted(nifty_rows['expiry'].unique())
    print("\n--- Available NIFTY Expiries ---")
    for e in expiries:
        if e >= datetime.now().date():
            print(f"{e}")
            subset = nifty_rows[(nifty_rows['expiry'] == e) & (nifty_rows['instrument_type'] == 'OPTIDX')]
            print(f"  Count: {len(subset)}")
            if len(subset) > 0:
                 strikes = subset['strike'].unique()
                 print(f"  Strikes Sample: {min(strikes)} ... {max(strikes)}")
            
else:
    print("No NIFTY rows found. Check 'name' column values.")
    print(df['name'].unique()[:10])

print("--------------------------------")
