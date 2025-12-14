import os
import sys
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv
from kiteconnect import KiteConnect

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

print("Downloading...")
instruments = kite.instruments("NFO")
df = pd.DataFrame(instruments)
df['expiry'] = pd.to_datetime(df['expiry']).dt.date

target_date = date(2025, 12, 16)
print(f"Looking for: {target_date}")

# Check if date exists at all
matches = df[df['expiry'] == target_date]
print(f"Rows matching date: {len(matches)}")

if not matches.empty:
    print("Sample rows:")
    # Print name and type
    print(matches[['name', 'instrument_type', 'strike']].head())
    
    # Check strict filter
    strict = matches[(matches['name'] == 'NIFTY') & (matches['instrument_type'] == 'OPTIDX')]
    print(f"Strict match (NIFTY + OPTIDX): {len(strict)}")
    if not strict.empty:
        print("Strikes present:")
        print(sorted(strict['strike'].unique())[:5])
        print(sorted(strict['strike'].unique())[-5:])
else:
    print("Date NOT found.")
    # Print nearby
    dates = sorted(df['expiry'].unique())
    print("Nearby available:")
    for d in dates:
        if d.year == 2025 and d.month == 12:
            print(d)
