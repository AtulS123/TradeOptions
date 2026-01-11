import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def black_scholes(S, K, T, r, sigma, option_type="CE"):
    """
    S: Spot Price
    K: Strike Price
    T: Time to Expiry (in years)
    r: Risk-free rate (decimal, e.g., 0.07)
    sigma: Volatility (decimal, e.g., 0.20 for 20% VIX)
    option_type: "CE" or "PE"
    """
    try:
        current_time = datetime.now().time()
        # Avoid division by zero
        if T <= 1e-5:
            # At expiry logic
            if option_type == "CE":
                return max(0, S - K)
            else:
                return max(0, K - S)
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == "CE":
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
        return max(0.05, price) # Min price 0.05
    except Exception as e:
        # logger.error(f"BS Error: {e}")
        return 0.0

def get_seconds_to_expiry(current_dt, expiry_day_of_week=3):
    """
    Finds next Thursday (3). 
    Adjust logic as needed for monthly etc. 
    For simplicity, we assume weekly expiry on Thursday.
    """
    # 0=Mon, 3=Thu, 6=Sun
    days_ahead = expiry_day_of_week - current_dt.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
        
    # If today is Thursday, check time? Assuming 15:30 expiry.
    # For simplicity, if today is Thursday, we might use next Thursday if near close?
    # Let's simple use strictly next Thursday logic from date perspectives
    
    # Correction: If today IS Thursday, days_ahead is 0, +7 = 7 days.
    # But if we are running intra-day Thursday, we want TODAY.
    if current_dt.weekday() == expiry_day_of_week:
        # If before 15:30, it is today.
        if current_dt.hour < 15 or (current_dt.hour == 15 and current_dt.minute < 30):
            days_ahead = 0
        else:
            days_ahead = 7

    target_date = current_dt + pd.Timedelta(days=days_ahead)
    expiry_dt = target_date.replace(hour=15, minute=30, second=0, microsecond=0)
    
    diff = (expiry_dt - current_dt).total_seconds()
    return max(0, diff)

def generate_synthetic_feed(spot_df: pd.DataFrame, vix_df: pd.DataFrame, risk_free_rate=0.07) -> pd.DataFrame:
    """
    Merges Spot and VIX, calculates ATM Strike, DTE, and Option Prices (CE/PE).
    Returns DataFrame with [datetime, open, high, low, close, call_price, put_price, ...].
    """
    logger.info("Generating Synthetic Options Feed...")
    
    # Ensure Datetime Index
    if 'datetime' not in spot_df.columns:
        spot_df = spot_df.reset_index()
    if 'datetime' not in vix_df.columns:
        vix_df = vix_df.reset_index()
        
    spot_df['datetime'] = pd.to_datetime(spot_df['datetime'])
    vix_df['datetime'] = pd.to_datetime(vix_df['datetime'])
    
    # Merge (Inner Join)
    merged = pd.merge(spot_df, vix_df, on='datetime', how='inner', suffixes=('', '_vix'))
    
    # Rename VIX close if needed
    if 'close_vix' in merged.columns:
        merged['vix'] = merged['close_vix']
    elif 'close' in vix_df.columns:
         # If no suffix collision (unlikely given suffixes), check VIX df structure
         # Assumes vix_df has 'close' which became 'close_vix'
         pass 

    # Prepare Columns
    # S = merged['close'] (Spot Close)
    # sigma = merged['vix'] / 100
    
    # Vectorized or Apply? Apply is easier for DTE logic
    
    results = []
    
    for idx, row in merged.iterrows():
        dt = row['datetime']
        spot = row['close']
        vix = row.get('vix', 20.0) # Default 20
        
        # 1. Calculate ATM Strike (Round to nearest 50)
        atm_strike = round(spot / 50) * 50
        
        # 2. DTE
        seconds_left = get_seconds_to_expiry(dt)
        years_left = seconds_left / (365 * 24 * 3600)
        
        # 3. Prices
        sigma = vix / 100.0
        
        c_price = black_scholes(spot, atm_strike, years_left, risk_free_rate, sigma, "CE")
        p_price = black_scholes(spot, atm_strike, years_left, risk_free_rate, sigma, "PE")
        
        # Append
        row_dict = row.to_dict()
        row_dict['nifty_close'] = spot # Alias for BacktestRunner
        row_dict['atm_strike'] = atm_strike
        row_dict['call_price'] = c_price
        row_dict['put_price'] = p_price
        results.append(row_dict)
        
    return pd.DataFrame(results)
