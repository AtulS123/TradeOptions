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
from src.utils.smart_selector import get_best_strike
from strategy_engine.strategy_manager import StrategyManager
from strategy_engine.strategies.vwap import VWAPStrategy
from risk.risk_manager import RiskManager
from state.state_manager import StateManager, JSONStateStore

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

# State Persistence
state_store = JSONStateStore()
state_manager = StateManager(state_store)

# Strategy Orchestrator
strategy_manager = StrategyManager()
vwap_strategy = VWAPStrategy() # The Plugin

# Risk Manager (Gatekeeper)
risk_manager = RiskManager(total_capital=100000.0)

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

            # --- Strategy Integration ---
            # Simulate a 'Tick' from the quote (Polling -> Tick Adapter)
            nifty_tick = {
                "instrument_token": spot_quote["NSE:NIFTY 50"]["instrument_token"],
                "last_price": nifty_ltp,
                "volume": spot_quote["NSE:NIFTY 50"]["volume"], # Cumulative
                "cumulative_volume": spot_quote["NSE:NIFTY 50"]["volume"],
                "timestamp": datetime.now()
            }
            
            # Pass to Orchestrator
            signals = strategy_manager.on_tick(nifty_tick)
            if signals:
                logger.info(f"SIGNALS GENERATED: {signals}")
            # ----------------------------

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
                    ce_token = int(ce_row.iloc[0]['instrument_token'])
                    pe_token = int(pe_row.iloc[0]['instrument_token'])
                    
                    tokens_to_fetch.extend([ce_token, pe_token])
                        'CE': {'token': ce_token, 'symbol': ce_row.iloc[0]['tradingsymbol']},
                        'PE': {'token': pe_token, 'symbol': pe_row.iloc[0]['tradingsymbol']}
                    }
            
            if not tokens_to_fetch:
                await asyncio.sleep(1)
                continue

            # 3. Fetch Quotes for all Options (and active positions - GHOST POSITION FIX)
            active_tokens = state_manager.get_active_tokens()
            # Merge lists
            all_tokens_to_poll = list(set(tokens_to_fetch + active_tokens))
            
            quotes = kite.quote(all_tokens_to_poll)
            
            # 4. Process Data & Calculate Greeks
            new_chain_data = []
            today = datetime.now()
            
            expiry_date = relevant_strikes.iloc[0]['expiry'] 
            
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
                    "putDelta": pe_delta,
                    "ce_token": ce_token,
                    "pe_token": pe_token
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
    
    # 0. Persistence Layer: Rehydrate
    logger.info("loading persistent state...")
    current_state = state_manager.load()
    
    # Rehydrate Risk Manager
    risk_manager.restore_state(current_state.daily_pnl, current_state.kill_switch_active)
    
    # Rehydrate Strategy Manager
    strategy_manager.restore_positions(current_state.open_positions)
    
    logger.info(f"System Rehydrated. Daily PnL: {current_state.daily_pnl}, Open Pos: {len(current_state.open_positions)}")
    
    # Plug the Strategy
    # To "Turn Off", just comment out this line:
    strategy_manager.register_strategy(vwap_strategy)
    
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

@app.get("/select-strike")
def select_strike_endpoint(type: str, delta: float):
    """
    Selects the best strike based on target Delta.
    Usage: /select-strike?type=CE&delta=0.5
    """
    # Validate type
    if type not in ["CE", "PE"]:
        return {"error": "Invalid option type. Use CE or PE."}
        
    result = get_best_strike(option_chain_data, type, delta)
    
    if not result:
        return {"error": "No suitable strike found within safety limits."}
        
    return result

@app.get("/validate-trade")
def validate_trade_endpoint(entry: float, sl: float, target: float):
    """
    Validates a trade setup and calculates position size.
    Usage: /validate-trade?entry=100&sl=90&target=120
    """
    # 1. Gatekeeper Check
    validation = risk_manager.validate_trade_setup(entry, sl, target)
    
    if not validation["approved"]:
        return validation
        
    # 2. Sizing Engine
    suggested_qty = risk_manager.get_target_size(entry, sl)
    
    return {
        "approved": True,
        "reason": "Approved",
        "suggested_qty": suggested_qty,
        "risk_manager_state": {
            "daily_pnl": risk_manager.daily_pnl,
            "kill_switch": risk_manager.kill_switch_active
        }
    }

@app.get("/system-state")
def get_system_state():
    """
    Debug endpoint to view raw persistence state.
    """
    return state_manager.get_state()

@app.get("/paper-trades")
def get_paper_trades():
    """
    Returns active paper trades with live P&L.
    """
    state = state_manager.get_state()
    positions = []
    
    # We rely on the global 'market_status' or need a cache. 
    # For robust implementation, we'll try to fetch fresh quotes for these specific tokens 
    # OR rely on the main loop having updated a cache.
    # Given the loop runs every 1s, let's just peek at what data we have.
    # BUT 'ticks' inside the loop is local. 
    # FAILSAFE: Fetch quote directly here to avoid potential race/staleness if loop allows.
    # Using 'kite.quote' is fast enough for < 10 items.
    
    active_tokens = state_manager.get_active_tokens()
    if not active_tokens:
        return []

    try:
        live_quotes = kite.quote(active_tokens)
    except Exception as e:
        logger.error(f"Failed to fetch live quotes for paper trades: {e}")
        live_quotes = {}

    for symbol, details in state.open_positions.items():
        # Details: {qty, entry, sl, target, token, strategy}
        token = details.get("token") # Assuming we saved token
        if not token: 
            # Fallback if token missing (shouldn't happen with correct usage)
            continue
            
        ltp = 0.0
        if int(token) in live_quotes:
            ltp = live_quotes[int(token)]['last_price']
        
        # Calculate PnL
        # Assuming Long Call/Put (Buy)
        # PnL = (Current - Entry) * Qty
        entry_price = details.get("entry_price", 0.0)
        qty = details.get("quantity", 0)
        
        # PnL Logic
        pnl = (ltp - entry_price) * qty if ltp > 0 else 0.0
        
        pos_data = {
            "id": str(token),
            "symbol": symbol, # e.g. NIFTY 24500 CE
            "strike": details.get("strike", 0),
            "type": details.get("option_type", "CE"),
            "action": "BUY", # Assuming we only buy for now
            "quantity": qty,
            "entryPrice": entry_price,
            "currentPrice": ltp,
            "stopLoss": details.get("stop_loss", 0),
            "target": details.get("target", 0),
            "timestamp": details.get("timestamp", datetime.now().isoformat()),
            "status": "active",
            "strategy": details.get("strategy_name", "Unknown"),
            "pnl": pnl
        }
        positions.append(pos_data)

    return positions

@app.delete("/trade/{token}")
def close_trade_manual(token: int):
    """
    Manually closes a trade, recording P&L.
    """
    state = state_manager.get_state()
    # Find active position by token
    target_symbol = None
    target_details = None
    
    for sym, details in state.open_positions.items():
        if int(details.get("token", 0)) == token:
            target_symbol = sym
            target_details = details
            break
            
    if not target_symbol:
        return {"status": "error", "message": "Trade not found"}

    # 1. Fetch Exit Price
    try:
        quote = kite.quote([token])
        exit_price = quote[token]['last_price']
    except:
        exit_price = target_details.get("entry_price") # Fallback to breakeven if fetch fails? Or 0? Better BE.
    
    # 2. Calc Realized PnL
    qty = target_details.get("quantity", 0)
    entry = target_details.get("entry_price", 0)
    pnl = (exit_price - entry) * qty
    
    # 3. Update PnL
    state_manager.update_pnl(pnl)
    
    # 4. Remove Position
    state_manager.close_position(target_symbol)
    
    # 5. Notify Strategy (Manual Exit)
    strategy_manager.force_exit(token)
    
    logger.info(f"Manual Close: {target_symbol}, PnL: {pnl}")
    return {"status": "success", "closed_at": exit_price, "pnl": pnl}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
