import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, date
from scipy.stats import norm
from dotenv import load_dotenv
from kiteconnect import KiteConnect

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("BS_Live_Test")

# Load Environment Variables
# Assuming .env is in logical root (parent of lab)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

if not API_KEY or not ACCESS_TOKEN:
    logger.error("Error: API_KEY or ACCESS_TOKEN not found in .env")
    sys.exit(1)

# Black-Scholes Function (Copied/Adapted from main.py)
def black_scholes_price(flag, S, K, T, r, sigma):
    """
    Calculate theoretical Black-Scholes price.
    flag: 'c' or 'p'
    S: Spot Price
    K: Strike Price
    T: Time to Expiry (in years)
    r: Risk-free rate
    sigma: Volatility (annualized)
    """
    try:
        if T <= 0 or S <= 0 or K <= 0:
            return 0.0
            
        d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if flag == 'c':
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    except Exception as e:
        logger.error(f"BS Calc Error: {e}")
        return 0.0

def main():
    print("\n--- Black-Scholes Live Verification ---\n")
    
    # 1. Input Expiry
    if len(sys.argv) > 1:
        expiry_str = sys.argv[1]
        print(f"Using Expiry from CLI: {expiry_str}")
    else:
        expiry_str = input("Enter Expiry Date (YYYY-MM-DD): ").strip()
        
    try:
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    except ValueError:
        logger.error("Invalid Date Format. Please use YYYY-MM-DD.")
        return

    # 2. Connect to Kite
    print("Connecting to Kite...")
    try:
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        # Verify
        profile = kite.profile()
        print(f"Connected as: {profile.get('user_name')}")
    except Exception as e:
        logger.error(f"Connection Failed: {e}")
        return

    # 3. Get Spot & VIX
    print("Fetching Spot and VIX...")
    try:
        # Need correct symbols. usually NSE:NIFTY 50 and NSE:INDIA VIX
        quotes = kite.quote(["NSE:NIFTY 50", "NSE:INDIA VIX"])
        
        if "NSE:NIFTY 50" not in quotes or "NSE:INDIA VIX" not in quotes:
            logger.error("Could not fetch NIFTY 50 or INDIA VIX quote.")
            # Debug: print keys
            print(f"Available keys: {quotes.keys()}")
            return
            
        nifty_ltp = quotes["NSE:NIFTY 50"]["last_price"]
        vix_ltp = quotes["NSE:INDIA VIX"]["last_price"]
        
        print(f"Spot: {nifty_ltp:,.2f} | VIX: {vix_ltp}")
        
    except Exception as e:
        logger.error(f"Data Fetch Error: {e}")
        return

    # 4. Calculate ATM Strike
    strike_step = 50
    atm_strike = round(nifty_ltp / strike_step) * strike_step
    print(f"ATM Strike: {atm_strike}")

    # 5. Find Instrument Token
    print("Finding Option Tokens...")
    try:
        instruments = kite.instruments("NFO")
        df = pd.DataFrame(instruments)
        
        # Filter
        # Name: NIFTY, Types: OPTIDX, Expiry: matched, Strike: matched
        df['expiry'] = pd.to_datetime(df['expiry']).dt.date
        
        # Debug: Check if expiry exists in DF
        available_expiries = df[df['name']=='NIFTY']['expiry'].unique()
        if expiry_date not in available_expiries:
            print(f"Warning: {expiry_date} not found in NIFTY expiries.")
            print(f"Available: {[str(d) for d in sorted(available_expiries) if d >= date.today()][:5]}")
        
        target_opts = df[
            (df['name'] == 'NIFTY') &
            (df['instrument_type'].isin(['CE', 'PE'])) &
            (df['expiry'] == expiry_date)
        ]
        
        if target_opts.empty:
             logger.error(f"No NIFTY Options (CE/PE) found for {expiry_date}")
             return

        # Fuzzy match strike
        # Find row where abs(strike - atm_strike) is minimal
        # If min diff is small (< 1.0), accept it.
        target_opts['diff'] = (target_opts['strike'] - atm_strike).abs()
        closest_row = target_opts.loc[target_opts['diff'].idxmin()]
        min_diff = closest_row['diff']
        
        if min_diff > 5.0: # If closest is > 5 points away, it's not the ATM we want
             logger.error(f"Exact ATM Strike {atm_strike} not found. Closest is {closest_row['strike']}")
             return
             
        # Now get CE and PE for this *actual* strike in the system
        actual_strike = closest_row['strike']
        print(f"Targeting Strike: {actual_strike}")
        
        ce_row = target_opts[(target_opts['strike'] == actual_strike) & (target_opts['instrument_type'] == 'CE')]
        pe_row = target_opts[(target_opts['strike'] == actual_strike) & (target_opts['instrument_type'] == 'PE')]
        
        if ce_row.empty or pe_row.empty:
            logger.error("Could not find both CE and PE instruments.")
            return
            
        ce_token = int(ce_row.iloc[0]['instrument_token'])
        ce_symbol = ce_row.iloc[0]['tradingsymbol']
        
        pe_token = int(pe_row.iloc[0]['instrument_token'])
        pe_symbol = pe_row.iloc[0]['tradingsymbol']
        
        print(f"Found: {ce_symbol} ({ce_token}) & {pe_symbol} ({pe_token})")
        
    except Exception as e:
        logger.error(f"Instrument Lookup Error: {e}")
        return

    # 6. Fetch Option Prices
    print("Fetching Option Prices...")
    try:
        opt_quotes = kite.quote([ce_token, pe_token])
        ce_ltp = opt_quotes[str(ce_token)]['last_price'] # kite returns str keys usually for ints
        pe_ltp = opt_quotes[str(pe_token)]['last_price'] if str(pe_token) in opt_quotes else opt_quotes[pe_token]['last_price']
        # Handle int/str key potential mismatch
        
    except Exception as e:
        logger.error(f"Option Quote Error: {e}")
        return

    # 7. Calculate BS Price
    # Time to expiry
    # Simple approx: (Expiry Date 15:30 - Now) / 365 days
    # Or just Days to Expiry / 365
    now = datetime.now()
    expiry_dt = datetime.combine(expiry_date, datetime.min.time()).replace(hour=15, minute=30)
    
    # If using just date diff:
    # time_to_expiry_days = (expiry_date - date.today()).days
    # But intra-day precision is better
    diff = expiry_dt - now
    days_to_expiry = diff.total_seconds() / (24 * 3600)
    T = days_to_expiry / 365.0
    
    # Rate
    r = 0.10 # 10%
    
    # Sigma
    sigma = vix_ltp / 100.0
    
    print("-" * 48)
    
    # Call
    bs_call = black_scholes_price('c', nifty_ltp, atm_strike, T, r, sigma)
    diff_ce = ce_ltp - bs_call
    skew_ce = (diff_ce / bs_call) * 100 if bs_call > 0 else 0
    
    print(f"CALL ({ce_symbol})")
    print(f"Real Market Price: Rs {ce_ltp:.2f}")
    print(f"Theoretical BS Price: Rs {bs_call:.2f}")
    print(f"Difference (Skew): {'+' if skew_ce > 0 else ''}{skew_ce:.1f}%")
    
    print("-" * 48)

    # Put
    bs_put = black_scholes_price('p', nifty_ltp, atm_strike, T, r, sigma)
    diff_pe = pe_ltp - bs_put
    skew_pe = (diff_pe / bs_put) * 100 if bs_put > 0 else 0
    
    print(f"PUT ({pe_symbol})")
    print(f"Real Market Price: Rs {pe_ltp:.2f}")
    print(f"Theoretical BS Price: Rs {bs_put:.2f}")
    print(f"Difference (Skew): {'+' if skew_pe > 0 else ''}{skew_pe:.1f}%")
    print("-" * 48)
    
    # Interpretation
    if skew_ce > 5:
        print("Note: Market is paying a significant premium (High IV for calls).")
    if skew_pe > 5:
        print("Note: Market is paying a significant premium (High IV for puts).")
        
if __name__ == "__main__":
    main()
