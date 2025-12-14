import os
import asyncio
import logging
import pandas as pd
from datetime import datetime, date
import time
from typing import List, Dict, Optional
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from kiteconnect import KiteConnect
from scipy.stats import norm
import numpy as np

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Environment Variables
load_dotenv()
API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

# Global State
kite: Optional[KiteConnect] = None
instrument_df: Optional[pd.DataFrame] = None
nifty_token: Optional[int] = None
option_chain_data: List[Dict] = []
market_status = {"status": "Disconnected", "nifty_price": 0.0, "pcr": 0.0}
is_server_running = True

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_nearest_expiry(df: pd.DataFrame) -> date:
    """Find the nearest upcoming expiry date."""
    today = date.today()
    all_expiries = sorted(df['expiry'].dropna().unique())
    future_expiries = [e for e in all_expiries if e >= today]
    if not future_expiries:
        raise ValueError("No future expiries found!")
    return future_expiries[0]

def black_scholes_greeks(flag, S, K, T, r, market_price):
    """
    Calculate Implied Volatility and Delta using Newton-Raphson method.
    """
    try:
        # Basic bounds check
        if T <= 0 or S <= 0 or K <= 0:
            return 0.0, 0.0
            
        # Delta calculation function
        def get_delta(sigma):
            d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            if flag == 'c':
                return norm.cdf(d1)
            else:
                return norm.cdf(d1) - 1

        # BS Price function
        def bs_price(sigma):
            d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            if flag == 'c':
                return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            else:
                return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        # Calculate IV using Newton-Raphson
        sigma = 0.5 # Initial guess
        for i in range(20): # reduced iterations for speed
            try:
                price = bs_price(sigma)
                diff = market_price - price
                if abs(diff) < 1e-4:
                    break
                    
                d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
                vega = S * norm.pdf(d1) * np.sqrt(T)
                
                if vega < 1e-8:
                    break
                    
                sigma = sigma + diff/vega
            except:
                break
            
        iv = max(0, sigma)
        delta_val = get_delta(iv)
        
        return round(iv * 100, 2), round(delta_val, 4)

    except Exception:
        return 0.0, 0.0

def calculate_greeks(option_type, s, k, t, r, price):
    flag = 'c' if option_type == 'CE' else 'p'
    return black_scholes_greeks(flag, s, k, t, r, price)

async def market_data_loop():
    """Background task to update market data every second."""
    global option_chain_data, market_status
    
    logger.info("Starting Market Data Loop...")
    
    while is_server_running:
        try:
            if kite is None or instrument_df is None:
                await asyncio.sleep(2)
                continue

            # 1. Fetch NIFTY 50 Spot Price
            spot_quote = kite.quote(["NSE:NIFTY 50"])
            if "NSE:NIFTY 50" not in spot_quote:
                logger.warning("Failed to fetch Nifty Spot")
                await asyncio.sleep(1)
                continue
                
            nifty_ltp = spot_quote["NSE:NIFTY 50"]["last_price"]
            market_status["nifty_price"] = nifty_ltp
            market_status["status"] = "Connected"

            # 2. Select 20 Strikes (10 up, 10 down) around ATM
            strike_step = 50
            atm_strike = round(nifty_ltp / strike_step) * strike_step
            
            min_strike = atm_strike - (10 * strike_step)
            max_strike = atm_strike + (10 * strike_step)
            
            relevant_strikes = instrument_df[
                (instrument_df['strike'] >= min_strike) & 
                (instrument_df['strike'] <= max_strike)
            ].sort_values('strike')
            
            unique_strikes = relevant_strikes['strike'].unique()
            
            # Prepare instrument tokens for fetching quotes
            tokens_to_fetch = []
            strike_map = {} # strike -> {CE_token: ..., PE_token: ...}
            
            for strike in unique_strikes:
                ce_row = relevant_strikes[(relevant_strikes['strike'] == strike) & (relevant_strikes['instrument_type'] == 'CE')]
                pe_row = relevant_strikes[(relevant_strikes['strike'] == strike) & (relevant_strikes['instrument_type'] == 'PE')]
                
                if not ce_row.empty and not pe_row.empty:
                    ce_token = ce_row.iloc[0]['instrument_token']
                    pe_token = pe_row.iloc[0]['instrument_token']
                    
                    tokens_to_fetch.extend([ce_token, pe_token])
                    strike_map[strike] = {
                        'CE': {'token': ce_token, 'symbol': ce_row.iloc[0]['tradingsymbol']},
                        'PE': {'token': pe_token, 'symbol': pe_row.iloc[0]['tradingsymbol']}
                    }
            
            if not tokens_to_fetch:
                await asyncio.sleep(1)
                continue

            # 3. Fetch Quotes for all Options
            quotes = kite.quote(tokens_to_fetch)
            
            # 4. Process Data & Calculate Greeks
            new_chain_data = []
            today = datetime.now()
            
            expiry_date = relevant_strikes.iloc[0]['expiry']
            expiry_dt = datetime.combine(expiry_date, datetime.min.time()).replace(hour=15, minute=30)
            
            diff_seconds = (expiry_dt - today).total_seconds()
            t_years = max(diff_seconds / (365 * 24 * 3600), 1e-9)
            
            r = 0.10 
            
            total_ce_oi = 0
            total_pe_oi = 0
            
            for strike, instruments in strike_map.items():
                ce_token = instruments['CE']['token']
                pe_token = instruments['PE']['token']
                
                ce_data = quotes.get(str(ce_token)) or quotes.get(ce_token)
                pe_data = quotes.get(str(pe_token)) or quotes.get(pe_token)
                
                if not ce_data or not pe_data:
                    continue
                    
                ce_ltp = ce_data['last_price']
                pe_ltp = pe_data['last_price']
                ce_oi = ce_data['oi']
                pe_oi = pe_data['oi']
                ce_vol = ce_data['volume']
                pe_vol = pe_data['volume']
                
                total_ce_oi += ce_oi
                total_pe_oi += pe_oi

                # Greeks
                ce_iv, ce_delta = calculate_greeks('CE', nifty_ltp, strike, t_years, r, ce_ltp)
                pe_iv, pe_delta = calculate_greeks('PE', nifty_ltp, strike, t_years, r, pe_ltp)
                
                new_chain_data.append({
                    "strike": float(strike),
                    "callOI": ce_oi,
                    "callVolume": ce_vol,
                    "callLTP": ce_ltp,
                    "callIV": ce_iv,
                    "callDelta": ce_delta,
                    "putLTP": pe_ltp,
                    "putIV": pe_iv,
                    "putVolume": pe_vol,
                    "putOI": pe_oi,
                    "putDelta": pe_delta
                })
            
            option_chain_data = sorted(new_chain_data, key=lambda x: x['strike'])
            
            # Calculate PCR
            if total_ce_oi > 0:
                market_status["pcr"] = round(total_pe_oi / total_ce_oi, 2)
            else:
                market_status["pcr"] = 0.0
                
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in market loop: {e}")
            await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    global kite, instrument_df, nifty_token, is_server_running
    is_server_running = True
    
    logger.info("Connecting to Kite Connect...")
    try:
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        
        # Test connection
        profile = kite.profile()
        logger.info(f"Connected as {profile.get('user_name')}")
        
        # Load Instruments
        logger.info("Downloading instruments...")
        instruments = kite.instruments("NFO")
        df = pd.DataFrame(instruments)
        
        # Filter for NIFTY
        df = df[df['name'] == 'NIFTY']
        
        # Parse expiry
        df['expiry'] = pd.to_datetime(df['expiry']).dt.date
        
        # Find nearest expiry
        nearest_expiry = get_nearest_expiry(df)
        logger.info(f"Nearest Expiry selected: {nearest_expiry}")
        
        # Filter for nearest expiry
        instrument_df = df[df['expiry'] == nearest_expiry]
        logger.info(f"Loaded {len(instrument_df)} contracts for {nearest_expiry}")
        
        # Start background task
        asyncio.create_task(market_data_loop())
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")

@app.on_event("shutdown")
def shutdown_event():
    global is_server_running
    is_server_running = False

@app.get("/market-status")
def get_market_status():
    return market_status

@app.get("/option-chain")
def get_option_chain():
    return option_chain_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
