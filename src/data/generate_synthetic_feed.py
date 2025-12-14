import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import timedelta
import os

def next_thursday(date_val):
    # Weekday: Mon=0, Thu=3, Sun=6
    day_of_week = date_val.weekday()
    if day_of_week == 3: # Thursday
        return date_val
    days_ahead = 3 - day_of_week
    if days_ahead < 0: # Today is Fri(4), Sat(5), Sun(6)
        days_ahead += 7
    return date_val + timedelta(days=days_ahead)

def calculate_black_scholes_vectorized(S, K, T, r, sigma):
    # Safety for T
    T = np.maximum(T, 1e-5)
    
    # Verify shapes
    count = len(S)
    # Ensure inputs are numpy arrays
    S = np.array(S)
    K = np.array(K)
    T = np.array(T)
    sigma = np.array(sigma)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    
    return call_price, put_price

def main():
    print("Loading data...")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, 'data')
    historical_dir = os.path.join(data_dir, 'historical')
    backtest_dir = os.path.join(data_dir, 'backtest')
    
    os.makedirs(backtest_dir, exist_ok=True)
    
    # Load Spot
    df_spot = pd.read_csv(os.path.join(historical_dir, 'nifty_spot_1min.csv'))
    df_spot['datetime'] = pd.to_datetime(df_spot.iloc[:, 0]) # Index 0
    df_spot = df_spot.set_index('datetime').sort_index()
    # Keep it simple, just renamed close
    df_spot = df_spot[['close']].rename(columns={'close': 'nifty_close'})
    
    # Load VIX
    df_vix = pd.read_csv(os.path.join(historical_dir, 'india_vix_1min.csv'))
    df_vix['datetime'] = pd.to_datetime(df_vix.iloc[:, 0])
    df_vix = df_vix.set_index('datetime').sort_index()
    df_vix = df_vix[['close']].rename(columns={'close': 'vix_close'})
    
    print("Merging data...")
    df = df_spot.join(df_vix, how='inner')
    print(f"Merged rows: {len(df)}")
    
    # 3. ATM Strike
    df['atm_strike'] = (round(df['nifty_close'] / 50) * 50).astype(int)
    
    print("Calculating DTE...")
    unique_dates = pd.Series(df.index.normalize().unique())
    next_thursdays = unique_dates.apply(lambda x: next_thursday(x))
    date_map = pd.Series(next_thursdays.values, index=unique_dates)
    
    # Assign target thursday to each row
    df['target_date'] = df.index.normalize().map(date_map)
    
    # Set expiry time to 15:30 on that date
    df['expiry_time'] = pd.to_datetime(df['target_date']) + timedelta(hours=15, minutes=30)
    
    # Calculate initial diff
    df['time_diff'] = df['expiry_time'] - df.index
    
    # Check for expired/negative (past 15:30 on Thursday)
    # Convert to seconds to check
    # Note: .dt accessor works on Series (df['time_diff'] is a Series)
    seconds_diff = df['time_diff'].dt.total_seconds()
    
    mask_expired = seconds_diff <= 0
    if mask_expired.any():
        print(f"Found {mask_expired.sum()} rows past expiry. Rolling to next week.")
        # Roll the expiry time forward by 7 days
        df.loc[mask_expired, 'expiry_time'] += timedelta(days=7)
        # Recalculate diff
        df['time_diff'] = df['expiry_time'] - df.index
    
    # Final DTE
    df['dte_days'] = df['time_diff'].dt.total_seconds() / (24 * 3600.0)
    df['T_years'] = df['dte_days'] / 365.0
    
    print("Calculating Black-Scholes...")
    sigma = df['vix_close'] / 100.0
    r = 0.07
    
    # Fill NaN just in case
    sigma = sigma.fillna(method='ffill').fillna(0.15) 
    
    c_p, p_p = calculate_black_scholes_vectorized(
        df['nifty_close'].values,
        df['atm_strike'].values,
        df['T_years'].values,
        r,
        sigma.values
    )
    
    multiplier = 1.06
    df['call_price'] = c_p * multiplier
    df['put_price'] = p_p * multiplier
    
    # Output
    out_cols = ['nifty_close', 'vix_close', 'atm_strike', 'dte_days', 'call_price', 'put_price']
    
    out_path = os.path.join(backtest_dir, 'synthetic_options.csv')
    print(f"Saving to {out_path}...")
    df[out_cols].to_csv(out_path)
    print("Done.")

if __name__ == "__main__":
    main()
