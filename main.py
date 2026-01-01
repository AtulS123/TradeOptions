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
from src.broker.paper_broker import PaperBroker
from src.data.trade_logger import TradeLogger

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
risk_manager = RiskManager(total_capital=200000.0)

# Execution Layer
paper_broker = PaperBroker(state_manager, slippage_pct=0.0005) # 0.05%
trade_logger = TradeLogger()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping")
def ping():
    return "pong"

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
                "volume": spot_quote["NSE:NIFTY 50"].get("volume", 0), # Cumulative
                "cumulative_volume": spot_quote["NSE:NIFTY 50"].get("volume", 0),
                "timestamp": datetime.now()
            }
            
            # Pass to Orchestrator
            signals = strategy_manager.on_tick(nifty_tick)
            
            # --- EXECUTION LOOP ---
            if signals:
                logger.info(f"SIGNALS RECEIVED: {signals}")
                
                for signal in signals:
                    # Signal: {action: BUY/SELL, tag: 'VWAP', type: 'LONG/SHORT'?}
                    # Assuming VWAP strategy returns 'action': 'BUY' for Long, 'SELL' for Short?
                    # Or 'signal': 1/-1?
                    # Let's align with VWAP strategy from earlier: 
                    # "signal": "BUY", "reason": ...
                    
                    # A. Signal Translation (Intent)
                    # If Strategy says BUY -> We want CALLS (Bullish)
                    # If Strategy says SELL -> We want PUTS (Bearish) - assuming 'SELL' means 'Short the Index'
                    
                    signal_action = signal.get("action")
                    intent_type = "CE" if signal_action == "BUY" else "PE"
                    
                    # B. Stop & Reverse Check
                    current_positions = state_manager.state.open_positions
                    
                    # Logic: 
                    # If Intent is CE, close any PE.
                    # If Intent is PE, close any CE.
                    
                    # Identify opposing positions
                    opposing_type = "PE" if intent_type == "CE" else "CE"
                    
                    for sym, pos in list(current_positions.items()):
                        # Check if position matches opposing type
                        # We stored 'option_type' in paper-trades endpoint logic, let's assume we store it in State too.
                        # If not, parse symbol? "NIFTY...CE"
                        pos_type = pos.get("option_type")
                        if not pos_type:
                            if "CE" in sym: pos_type = "CE"
                            elif "PE" in sym: pos_type = "PE"
                            
                        if pos_type == opposing_type:
                            logger.info(f"STOP & REVERSE: Closing opposing {pos_type} position {sym}")
                            # Close it
                            token = pos.get("token")
                            
                            # Fetch Exit Price (Slippage handled by Broker)
                            # We need *real* LTP to pass to Broker? Broker takes 'price' as LTP and applies slippage.
                            quote = kite.quote([token])
                            exit_ltp = quote[token]['last_price']
                            
                            # Execute Exit
                            exec_result = paper_broker.place_order(
                                symbol=sym,
                                quantity=pos.get("quantity"),
                                side="SELL",
                                price=exit_ltp
                            )
                            
                            # Calc Realized PnL
                            entry_price = pos.get("entry_price")
                            # Net PnL = (Exit - Entry) * Qty - Costs
                            # rough pnl for state manager
                            gross_pnl = (exec_result["average_price"] - entry_price) * pos.get("quantity")
                            net_pnl = gross_pnl - exec_result["costs"]
                            
                            state_manager.update_pnl(net_pnl)
                            state_manager.close_position(sym)
                            trade_logger.log_trade(
                                order_id=exec_result["order_id"],
                                symbol=sym,
                                action="SELL",
                                quantity=pos.get("quantity"),
                                price=exec_result["average_price"],
                                slippage=exec_result["slippage"],
                                costs=exec_result["costs"],
                                strategy_tag="REVERSAL"
                            )

                    # C. Strike Selection
                    # Only open NEW if we don't already hold this side?
                    # Simplify: If we don't hold Intent Type, Open it.
                    already_holding = False
                    for sym, pos in current_positions.items():
                        if intent_type in sym: 
                            already_holding = True
                            break
                            
                    if not already_holding:
                        selected_strike = get_best_strike(option_chain_data, intent_type, 0.55)
                        
                        if selected_strike:
                            # D. Risk Sizing (10% Rule)
                            entry_ltp = selected_strike["ltp"]
                            stop_loss_price = entry_ltp * 0.90 # 10% SL
                            
                            # Validation
                            validation = risk_manager.validate_trade_setup(entry_ltp, stop_loss_price, entry_ltp * 1.2) # Target irrelevant for calculation but needed for validation
                            
                            if validation["approved"]:
                                qty = risk_manager.get_target_size(entry_ltp, stop_loss_price)
                                
                                if qty >= 25: # Min 1 lot
                                    # E. Execution
                                    exec_result = paper_broker.place_order(
                                        symbol=selected_strike["symbol"],
                                        quantity=qty,
                                        side="BUY",
                                        price=entry_ltp
                                    )
                                    
                                    # F. Persistence
                                    state_manager.add_position(selected_strike["symbol"], {
                                        "token": selected_strike["token"],
                                        "symbol": selected_strike["symbol"],
                                        "quantity": qty,
                                        "entry_price": exec_result["average_price"], # Use actual executed price
                                        "stop_loss": stop_loss_price,
                                        "target": entry_ltp * 1.2, # Placeholder
                                        "option_type": intent_type,
                                        "strategy_name": signal.get("tag", "VWAP"),
                                        "timestamp": datetime.now().isoformat()
                                    })
                                    
                                    trade_logger.log_trade(
                                        order_id=exec_result["order_id"],
                                        symbol=selected_strike["symbol"],
                                        action="BUY",
                                        quantity=qty,
                                        price=exec_result["average_price"],
                                        slippage=exec_result["slippage"],
                                        costs=exec_result["costs"],
                                        strategy_tag=signal.get("tag", "VWAP")
                                    )
                                    logger.info(f"ENTRY EXECUTED: {selected_strike['symbol']} Qty: {qty}")
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
                    strike_map[strike] = {
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
                ce_vol = ce_data.get('volume', 0)
                pe_vol = pe_data.get('volume', 0)
                
                total_ce_oi += ce_oi
                total_pe_oi += pe_oi

                # Fetch Lot Size
                # We can grab it from 'relevant_strikes' or 'instrument_df'
                # Assuming all Nifty contracts have same lot size for this expiry
                lot_size = int(relevant_strikes.iloc[0]['lot_size'])

                # Greeks
                # Calculate Time to Expiry in Years
                expiry_dt = datetime.combine(expiry_date, datetime.min.time())
                now = datetime.now()
                diff = expiry_dt - now
                days_to_expiry = max(diff.days + (diff.seconds / 86400.0), 1e-5) # Avoid div by zero
                t_years = days_to_expiry / 365.0
                r = 0.10 # 10% Risk Free Rate assumption
                ce_iv, ce_delta = calculate_greeks('CE', nifty_ltp, strike, t_years, r, ce_ltp)
                pe_iv, pe_delta = calculate_greeks('PE', nifty_ltp, strike, t_years, r, pe_ltp)
                
                new_chain_data.append({
                    "strike": float(strike),
                    "callOI": int(ce_oi / lot_size), # Convert to Contracts/Lots
                    "callVolume": ce_vol,
                    "callLTP": ce_ltp,
                    "callIV": ce_iv,
                    "callDelta": ce_delta,
                    "putLTP": pe_ltp,
                    "putIV": pe_iv,
                    "putVolume": pe_vol,
                    "putOI": int(pe_oi / lot_size), # Convert to Contracts/Lots
                    "putDelta": pe_delta,
                    "ce_token": ce_token,
                    "pe_token": pe_token
                })
            
            option_chain_data = sorted(new_chain_data, key=lambda x: x['strike'])
            
            # Calculate PCR (Volume or OI based?) Usually OI.
            # Using raw OI sum for PCR calculation to preserve precision or use converted?
            # Ratio is same.
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
    
    logger.info("Connecting to Kite Connect...")
    try:
        final_access_token = ACCESS_TOKEN
        
        # Check for file-based token override
        token_file = "access_token.txt"
        if os.path.exists(token_file):
            try:
                with open(token_file, "r") as f:
                    file_token = f.read().strip()
                if file_token:
                    final_access_token = file_token
                    logger.info(f"Loaded Access Token from {token_file}")
            except Exception as e:
                logger.warning(f"Failed to read {token_file}: {e}")

        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(final_access_token)
        
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
        
        # --- VWAP COLD START FIX ---
        # Get NIFTY 50 Token
        # Need to query instruments for NSE:NIFTY 50 to get token
        # We can optimize by fetching 'NSE' instruments or just hardcoding/searching.
        # But 'kite.instruments("NSE")' is heavy.
        # Let's search 'spot_quote' logic later? No, we need it now.
        # Actually, we can fetch the token from 'quote' if we don't have it, but for historical we need token.
        # Efficient way: quote first.
        
        try:
            spot_q = kite.quote(["NSE:NIFTY 50"])
            nifty_token = spot_q["NSE:NIFTY 50"]["instrument_token"]
            
            logger.info(f"Fetching Historical Data for VWAP Seeding (Token: {nifty_token})...")
            
            # Fetch for today from 9:15 AM
            today_start = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
            now = datetime.now()
            
            if now > today_start:
                historical_data = kite.historical_data(
                    nifty_token, 
                    from_date=today_start, 
                    to_date=now, 
                    interval="minute"
                )
                
                # Convert to DF
                hist_df = pd.DataFrame(historical_data)
                
                # Seed VWAP (Register strategy first!)
                strategy_manager.register_strategy(vwap_strategy) # Plug IN before seeding
                vwap_strategy.seed_candles(hist_df)
            else:
                logger.info("Market not open yet, skipping VWAP seed.")
                strategy_manager.register_strategy(vwap_strategy)

        except Exception as e:
            logger.error(f"Failed to seed VWAP: {e}")
            # Ensure strategy registered even if seed fails
            strategy_manager.register_strategy(vwap_strategy)

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
    
    for sym, details in state.open_positions.items():
        if int(details.get("token", 0)) == token:
            target_symbol = sym
            break
            
    if not target_symbol:
        return {"status": "error", "message": "Trade not found"}

    # Use PaperBroker to close (Handles PnL, State, Logging)
    try:
        # We need current Price for accurate PnL record in Manual Close
        # Broker close_position takes 'price' as the market price to execute at.
        quote = kite.quote([token])
        exit_price = quote[token]['last_price']
        
        result = paper_broker.close_position(target_symbol, price=exit_price, reason="Manual API Close")
        return result
        
    except Exception as e:
        logger.error(f"Manual Close Error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/manual-trade")
def place_manual_trade(type: str = "CE", quantity: Optional[int] = None):
    """
    Manually triggers a paper trade for the best strike.
    """
    global option_chain_data, market_status
    
    # 1. Get Market Context
    if market_status["nifty_price"] == 0:
        return {"status": "error", "message": "Market data not yet available"}
        
    s = market_status["nifty_price"]
    
    # 2. Select Strike (ATM)
    # Reuse simple logic or get_best_strike
    # Let's use get_best_strike with Delta ~0.5 (ATM)
    target_strike = get_best_strike(option_chain_data, type, 0.55) 
    
    if not target_strike:
         return {"status": "error", "message": "No suitable strike found"}
         
    entry_ltp = target_strike["ltp"]
    stop_loss = entry_ltp * 0.90
    
    # 3. Sizing
    if quantity:
        qty = quantity
    else:
        qty = risk_manager.get_target_size(entry_ltp, stop_loss)
        if qty < 25: qty = 25 # Min 1 lot
        
    # 4. Execute
    try:
        exec_result = paper_broker.place_order(
            symbol=target_strike["symbol"],
            quantity=qty,
            side="BUY",
            price=entry_ltp
        )
        
        # 5. Persist
        state_manager.add_position(target_strike["symbol"], {
            "token": target_strike["token"],
            "symbol": target_strike["symbol"],
            "quantity": qty,
            "entry_price": exec_result["average_price"],
            "stop_loss": stop_loss,
            "target": entry_ltp * 1.2,
            "option_type": type,
            "strategy_name": "MANUAL",
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "status": "success", 
            "trade": exec_result,
            "strike": target_strike["symbol"]
        }
    except Exception as e:
        logger.error(f"Manual Trade Failed: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
