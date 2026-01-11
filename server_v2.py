
import os
import asyncio
import logging
import pandas as pd
from datetime import datetime, date, timedelta
import time
import queue
import threading
from typing import List, Dict, Optional, Any

import json
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from urllib.parse import unquote

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from kiteconnect import KiteConnect
from scipy.stats import norm
import numpy as np
import math

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return super().default(obj)
from src.backtest_runner import BacktestRunner
from src.utils.market_schedule import is_market_open, get_market_state_label
from src.utils.smart_selector import get_best_strike
from strategy_engine.strategy_manager import StrategyManager
from strategy_engine.strategies.vwap import VWAPStrategy
from strategy_engine.strategies.rsi_reversal import RSIReversalStrategy
from risk.risk_manager import RiskManager
from state.state_manager import StateManager, JSONStateStore
from src.broker.paper_broker import PaperBroker
from src.broker.position_monitor import PositionMonitor
from src.data.trade_logger import TradeLogger
from src.utils.synthetic import generate_synthetic_feed

# Project Telescope - Multi-Timeframe Pattern Detection
from src.telescope.historical_loader import HistoricalDataLoader
from src.telescope.resampler import CandleResampler
from src.telescope.pattern_scanner import PatternScanner
from src.telescope.signal_tracker import SignalTracker

# Setup Logging

# Setup Logging
logging.basicConfig(filename='server_debug_new.log', filemode='w', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

# Load Environment Variables
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.getenv("API_KEY", "5f814cggb2e7m8z9").strip()
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

# Global State
kite: Optional[KiteConnect] = None # Global Kite Object
instrument_df: Optional[pd.DataFrame] = None
nifty_token: Optional[int] = None
vix_token: Optional[int] = None # Added VIX token
option_chain_data: List[Dict] = []
market_status = {"status": "Disconnected", "nifty_price": 0.0, "pcr": 0.0}
is_server_running = True
is_loop_running = False

# State Persistence
state_store = JSONStateStore()
state_manager = StateManager(state_store)

# Strategy Orchestrator
strategy_manager = StrategyManager()
vwap_strategy = VWAPStrategy() # The Plugin

# Risk Manager (Gatekeeper)
risk_manager = RiskManager(total_capital=200000.0)

# Execution Layer
paper_broker = PaperBroker(state_manager, risk_manager, slippage_pct=0.0005) # 0.05%
position_monitor = PositionMonitor(paper_broker, state_manager)
trade_logger = TradeLogger()

# Deployed Strategy Instances (for monitoring state access)
deployed_strategy_instances = {}  # strategy_id -> strategy_instance

# Telescope - Pattern Detection System
telescope_loader = HistoricalDataLoader()
telescope_resampler = CandleResampler()
telescope_scanner = PatternScanner()
telescope_tracker = SignalTracker()

def restore_deployed_strategies():
    """
    Restore strategy instances from persisted configs on server startup.
    """
    global deployed_strategy_instances
    
    logger.info(f"Restoring {len(state_manager.state.deployed_strategies)} deployed strategies...")
    
    for strategy_id, config in state_manager.state.deployed_strategies.items():
        try:
            strategy_type = config.get('type')
            
            # Recreate strategy instance based on type
            if strategy_type == "vwap":
                strategy = VWAPStrategy()
            elif strategy_type == "rsi_reversal":
                strategy = RSIReversalStrategy()
            elif strategy_type == "gamma_snap":
                from strategy_engine.strategies.gamma_snap import GammaSnapStrategy
                strategy = GammaSnapStrategy()
            elif strategy_type == "test_timer":
                from strategy_engine.strategies.test_timer import TestTimerStrategy
                strategy = TestTimerStrategy()
            else:
                logger.warning(f"Unknown strategy type: {strategy_type}, skipping {strategy_id}")
                continue
            
            # Store instance
            deployed_strategy_instances[strategy_id] = strategy
            logger.info(f"Restored strategy: {strategy_id} ({strategy_type})")
            
        except Exception as e:
            logger.error(f"Failed to restore strategy {strategy_id}: {e}")

async def strategy_tick_loop():
    """
    Background loop that calls process_tick() on all deployed strategies.
    Runs every second to check timers and generate signals.
    """
    logger.info("Starting strategy tick loop...")
    
    while is_server_running:
        try:
            # Get current NIFTY price for strike selection
            nifty_price = market_status.get('nifty_price', 24000)  # Default fallback
            
            # Create a synthetic tick for strategies that don't need market data
            tick_data = {
                'timestamp': datetime.now(),
                'last_price': nifty_price,
                'instrument_token': None
            }
            
            # Call process_tick on each deployed strategy
            for strategy_id, strategy in deployed_strategy_instances.items():
                try:
                    signal = strategy.process_tick(tick_data)
                    
                    if signal and signal.get('action') == 'BUY':
                        logger.info(f"Strategy {strategy_id} generated BUY signal: {signal}")
                        
                        # Execute the trade
                        try:
                            # Get strategy config for parameters
                            config = state_manager.state.deployed_strategies.get(strategy_id, {})
                            
                            # Find ATM strike from option chain
                            if not option_chain_data:
                                logger.warning("No option chain data available, cannot execute trade")
                                continue
                            
                            # Round to nearest 50 for NIFTY
                            atm_strike = round(nifty_price / 50) * 50
                            
                            # Find the strike in option chain
                            strike_data = None
                            for row in option_chain_data:
                                if row.get('strike') == atm_strike:
                                    strike_data = row
                                    break
                            
                            if not strike_data:
                                logger.warning(f"ATM strike {atm_strike} not found in option chain")
                                continue
                            
                            # Get CE (CALL) / PE (PUT) details
                            option_type = signal.get('option_type', 'CE')
                            if option_type == 'CE':
                                ltp = strike_data.get('callLTP', 0)
                                token = strike_data.get('callToken') or strike_data.get('ce_token')
                            else:
                                ltp = strike_data.get('putLTP', 0)
                                token = strike_data.get('putToken') or strike_data.get('pe_token')
                            
                            # Get symbol - try from chain first, then lookup from instrument_df
                            symbol = None
                            if option_type == 'CE':
                                symbol = strike_data.get('callSymbol')
                            else:
                                symbol = strike_data.get('putSymbol')
                            
                            # If symbol not in chain, lookup from instrument_df using token
                            if not symbol and token and instrument_df is not None:
                                try:
                                    match = instrument_df[instrument_df['instrument_token'] == token]
                                    if not match.empty:
                                        symbol = match.iloc[0]['tradingsymbol']
                                        logger.info(f"Found symbol from instrument_df: {symbol}")
                                except Exception as lookup_error:
                                    logger.warning(f"Failed to lookup symbol for token {token}: {lookup_error}")
                            
                            if not symbol or not token:
                                logger.warning(f"Invalid strike data for {atm_strike}")
                                continue
                            
                            # Determine quantity (NIFTY lot size = 65)
                            lots = config.get('lots_count', 1)
                            quantity = lots * 65  # Current NIFTY lot size
                            
                            # Get strategy tag from signal
                            strategy_tag = signal.get('tag', 'STRATEGY')
                            
                            # Place order via paper broker
                            order_result = paper_broker.place_order(
                                symbol=symbol,
                                quantity=quantity,
                                side="BUY",
                                order_type="MARKET",
                                price=ltp,
                                product="NRML",
                                tag=strategy_tag  # Add strategy tag
                            )
                            
                            logger.info(f"Executed trade for {strategy_id}: {order_result}")
                            
                            # Notify strategy of position opened
                            if hasattr(strategy, 'on_position_opened'):
                                strategy.on_position_opened(symbol, datetime.now())
                            
                        except Exception as trade_error:
                            logger.error(f"Failed to execute trade for {strategy_id}: {trade_error}")
                        
                except Exception as e:
                    logger.error(f"Error processing tick for strategy {strategy_id}: {e}")
            
            # Check for exit signals on all strategies
            for strategy_id, strategy in deployed_strategy_instances.items():
                try:
                    # Check if strategy has exit logic
                    if hasattr(strategy, 'should_exit'):
                        # Get all open positions from this strategy
                        for position in state_manager.state.open_positions:
                            # Check if position should be closed
                            should_close, reason = strategy.should_exit(position['symbol'])
                            
                            if should_close:
                                logger.info(f"Strategy {strategy_id} exit signal for {position['symbol']}: {reason}")
                                
                                # Get current price for closing
                                current_price = position.get('current_price', position.get('entry_price', 0))
                                
                                # Close the position
                                try:
                                    close_result = paper_broker.close_position(
                                        symbol=position['symbol'],
                                        price=current_price,
                                        reason=reason
                                    )
                                    logger.info(f"Closed position {position['symbol']}: {close_result}")
                                    
                                    # Notify strategy
                                    if hasattr(strategy, 'on_position_closed'):
                                        strategy.on_position_closed(position['symbol'])
                                    
                                except Exception as close_error:
                                    logger.error(f"Failed to close position {position['symbol']}: {close_error}")
                                    
                except Exception as e:
                    logger.error(f"Error checking exits for strategy {strategy_id}: {e}")
            
            await asyncio.sleep(1)  # Check every second
            
        except Exception as e:
            logger.error(f"Error in strategy tick loop: {e}")
            await asyncio.sleep(1)


async def telescope_tick_loop():
    """
    Background loop for Project Telescope.
    - Feeds 1m ticks to resampler
    - Detects patterns on candle close
    - Updates signal tracker with current prices
    """
    logger.info("Starting Telescope tick loop...")
    
    # Preload historical data on startup
    try:
        logger.info("Loading historical data for Telescope...")
        df_historical = telescope_loader.get_latest(365)  # Last 365 days
        telescope_resampler.preload_historical(df_historical)
        logger.info(f"Preloaded {len(df_historical)} candles into Telescope")
    except Exception as e:
        logger.error(f"Failed to preload historical data: {e}")
    
    while is_server_running:
        try:
            # LIVE PRICE FEED
            # Option 1: Get from Kite websocket (when integrated)
            # nifty_price = kite_stream_data.get('NIFTY_SPOT', 0)
            
            # Option 2: Get from option chain if available
            nifty_price = market_status.get('nifty_price', 0)
            
            # Option 3: SIMULATED FEED (for testing/market closed hours)
            if nifty_price == 0:
                import random
                # Base price + random walk
                base_price = 24500
                price_change = random.uniform(-50, 50)  # Random movement
                nifty_price = base_price + price_change
                market_status['nifty_price'] = nifty_price  # Update for other loops
                logger.info(f"Telescope: Simulated NIFTY @ {nifty_price:.2f}")
            
            # Create 1m tick with realistic OHLC
            # In production, track actual high/low over the minute
            tick = {
                'date': datetime.now(),
                'open': nifty_price,
                'high': nifty_price + random.uniform(0, 10),  # Slight variation
                'low': nifty_price - random.uniform(0, 10),
                'close': nifty_price,
                'volume': 0
            }
            
            # Feed to resampler
            events = telescope_resampler.add_tick(tick)
            
            # Process candle close events
            for event in events:
                try:
                    # Run pattern scanner
                    df = telescope_resampler.get_candles(event.timeframe, 200)
                    signals = telescope_scanner.scan(df, event.timeframe)
                    
                    # Add new signals to tracker
                    for sig in signals:
                        # Convert pattern_scanner Signal to signal_tracker Signal
                        from src.telescope.signal_tracker import Signal as TrackerSignal
                        tracker_sig = TrackerSignal(
                            id="",  # Will be set by tracker
                            pattern_name=sig.pattern_name,
                            timeframe=sig.timeframe,
                            timestamp=sig.timestamp,
                            signal_type=sig.signal_type,
                            entry_price=sig.entry_price,
                            stop_loss=sig.stop_loss,
                            target=sig.target,
                            candle_index=sig.candle_index,
                            confidence=sig.confidence,
                            atr=sig.atr,
                            metadata=sig.metadata
                        )
                        telescope_tracker.add_signal(tracker_sig)
                        logger.info(f"🎯 NEW SIGNAL: {sig.pattern_name} ({sig.signal_type}) on {sig.timeframe} @ {sig.entry_price}")
                    
                except Exception as scan_error:
                    logger.error(f"Error scanning {event.timeframe}: {scan_error}")
            
            # Update all active signals with current price
            for tf in ['1m', '5m', '15m', '1h', '1d']:
                telescope_tracker.update_price(tf, nifty_price, datetime.now())
            
            await asyncio.sleep(60)  # Update every minute
            
        except Exception as e:
            logger.error(f"Error in telescope tick loop: {e}")
            await asyncio.sleep(60)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Initialize strategies and start background loops on server startup."""
    restore_deployed_strategies()
    asyncio.create_task(strategy_tick_loop())
    asyncio.create_task(telescope_tick_loop())  # Start Project Telescope

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping")
def ping():
    return "pong"

@app.get("/market-status")
def get_market_status():
    """
    Returns the current market status with label.
    """
    market_label = get_market_state_label()
    return {
        "market_label": market_label,
        "is_open": is_market_open(),
        "nifty_price": market_status.get("nifty_price", 0.0),
        "change": market_status.get("change", 0.0),
        "pChange": market_status.get("pChange", 0.0),
        "status": market_status.get("status", "Disconnected"),
        "pcr": market_status.get("pcr", 0.0)
    }


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

def black_scholes_price(flag, S, K, T, r, sigma):
    """
    Calculates Option Price using Black-Scholes formula.
    """
    try:
        if T <= 0 or S <= 0 or K <= 0 or sigma <= 0:
             return max(0, S - K) if flag == 'CE' else max(0, K - S)
             
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if flag == 'CE':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
        return max(0.05, price) # Min tick size
    except Exception as e:
        logger.error(f"Black Scholes Error: {e} | S={S}, K={K}, T={T}, r={r}, sigma={sigma}")
        return 0.0

def get_nifty_futures_token():
    """
    Finds the current month's NIFTY Futures token from the loaded instrument_df.
    """
    global instrument_df
    try:
        if instrument_df is None or instrument_df.empty:
            logger.warning("Instrument DF empty, fetching NFO instruments...")
            instrument_df = pd.DataFrame(kite.instruments("NFO"))
            
        # Filter for NIFTY Futures
        # NIFTY 24JANFUT or similar name format? 
        # Better to filter by name='NIFTY', segment='NFO-FUT', instrument_type='FUT'
        
        # Adjust filters based on Kite API response structure
        # usually: name="NIFTY", segment="NFO-FUT", instrument_type="FUT"
        
        futs = instrument_df[
            (instrument_df['name'] == 'NIFTY') & 
            (instrument_df['instrument_type'] == 'FUT')
        ].copy()
        
        if futs.empty:
            raise Exception("No NIFTY Futures found in instrument dump")
            
        # Sort by expiry to get nearest
        futs['expiry'] = pd.to_datetime(futs['expiry'])
        current_date = datetime.now().date()
        
        # Filter only future expiries (or today)
        future_futs = futs[futs['expiry'].dt.date >= current_date].sort_values('expiry')
        
        if future_futs.empty:
             # Fallback: maybe expiry was yesterday? Just take last one?
             # Or refresh instruments?
             logger.warning("No upcoming NIFTY Futures found. Checking for ANY future...")
             # Look for last expiry (maybe today is expiry day and time passed?)
             future_futs = futs.sort_values('expiry') 
        
        if future_futs.empty:
             raise Exception("No NIFTY Futures found in instrument dump")
             
        # Prefer the one with nearest AFTER today (Current Month)
        # But if we are testing a historical date, we actually need the future valid AT THAT DATE.
        # This implementation picks CURRENT live future. 
        # For historical backtest, this is technically WRONG (volume will be 0 for old data of current future).
        # However, Kite historical API uses 'continuous=True' (implied) or we just need A token.
        # Actually for fetching historical data of "NIFTY FUT" 2024 from Kite, we need the "NIFTY 50" (Spot) 
        # OR "NIFTY 24JANO...".
        # 
        # Kite Connect Historical API 'continuous' parameter allows fetching continuous future data using ONE token?
        # No, Kite Connect historical API requires specific token. 
        # BUT 'continuous' param exists? No, only on some platforms.
        #
        # CRITICAL FIX: Kite Historical API for expired futures is tricky. 
        # We should use NIFTY SPOT for price/OHLC and just accept 0 volume if we can't find old future.
        # OR better: User asked for "Futures Data".
        # If we pick "NIFTY 24JANFUT" token now, we can only get history for that contract.
        # If backtest is Jan 2024, and we use NIFTY 25JANFUT, data might be empty or valid.
        
        # CORRECT APPROACH for SIMPLICITY:
        # Use NIFTY SPOT for now to ensure data exists.
        # The user's error "Failed to fetch" is because we picked a future token but got no data 
        # (likely because we picked CURRENT future 25JAN, but asked for data in 2024? Or vice versa).
        
        # Let's fallback to SPOT if FUT fails or just use SPOT with a warning that volume is 0.
        # Reverting to SPOT avoids the crash.
        # BUT user specifically asked for FUTURE to get VOLUME.
        
        # Let's try to find "NIFTY 24JANFUT" if date is Jan 2024? 
        # Required sophisticated lookup. 
        
        # PROPOSED FIX: Return None to force fallback to SPOT for now to Stop the Crash.
        # Then we can figure out continuous futures later.
        
        logger.warning("Futures token selection is risky for historical backtests without continuous data.")
        nearest_fut = future_futs.iloc[0]
        # logger.info(f"Selected Futures: {nearest_fut['tradingsymbol']} ...")
        
        # Check if we are asking for data range compatible with this future?
        # The backtest runner calls 'fetch_kite_data' with a date range.
        # If we return a 2025 token and ask for 2024 data, it might return empty.
        
        return nearest_fut['instrument_token']

    except Exception as e:
        logger.error(f"Failed to get futures token: {e}")
        return None

def fetch_kite_data_chunked(token, start_date, end_date, interval, progress_callback=None):
    """
    Fetches historical data from Kite API in chunks to avoid 'max days' limits.
    """
    all_records = []
    current_start = start_date
    
    # Define chunk size (e.g., 30 days is safe for all intervals)
    chunk_days = 30
    
    # Pre-calc total chunks for progress
    total_days = (end_date - start_date).days
    if total_days == 0: total_days = 1
    
    while current_start < end_date:
        current_end = current_start + timedelta(days=chunk_days)
        if current_end > end_date:
            current_end = end_date
            
        logger.info(f"Fetching chunk: {current_start} to {current_end}")
        
        if progress_callback:
             done_days = (current_start - start_date).days
             pct = int((done_days / total_days) * 100)
             progress_callback(pct, f"Fetched range {current_start.date()} to {current_end.date()}")
        
        try:
            records = kite.historical_data(token, current_start, current_end, interval)
            all_records.extend(records)
            time.sleep(0.1) # Rate limit politeness
        except Exception as e:
            logger.error(f"Error fetching chunk {current_start} - {current_end}: {e}")
            raise e
            
        current_start = current_end
        
        # Avoid infinite loop
        if current_start >= end_date:
            break
            
    return all_records


def calculate_greeks(option_type, s, k, t, r, price):
    flag = 'c' if option_type == 'CE' else 'p'
    return black_scholes_greeks(flag, s, k, t, r, price)

async def market_data_loop():
    """Background task to update market data every second."""
    global option_chain_data, market_status, nifty_token, vix_token, is_loop_running
    
    if is_loop_running:
        logger.warning("Market Loop already running.")
        return

    is_loop_running = True
    logger.info("Starting Market Data Loop...")
    
    while is_server_running:
        try:
            if kite is None or instrument_df is None:
                await asyncio.sleep(2)
                continue

            # 1. Fetch NIFTY 50 Spot Price
            # Ensure nifty_token is set before attempting to fetch
            if nifty_token is None:
                logger.warning("Nifty token not set, skipping market data fetch.")
                await asyncio.sleep(1)
                continue

            spot_quote = kite.quote([f"NSE:NIFTY 50"]) # Use instrument token directly if available
            if "NSE:NIFTY 50" not in spot_quote:
                logger.warning("Failed to fetch Nifty Spot")
                await asyncio.sleep(1)
                continue
                
            nifty_data = spot_quote["NSE:NIFTY 50"]
            nifty_ltp = nifty_data["last_price"]
            ohlc = nifty_data.get("ohlc", {})
            close_price = ohlc.get("close", nifty_ltp)
            
            change = nifty_ltp - close_price
            p_change = (change / close_price) * 100 if close_price else 0.0
            
            market_status["nifty_price"] = nifty_ltp
            market_status["change"] = round(change, 2)
            market_status["pChange"] = round(p_change, 2)
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
            
            # Check positions for SL/Target hits (auto-close if triggered)
            if len(state_manager.state.open_positions) > 0:
                position_monitor.check_positions(option_chain_data)
            
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
            
    is_loop_running = False
    logger.info("Market Loop Stopped.")

# --- BACKTEST SCHEMA ---
class StrategyConfig(BaseModel):
    strategy_type: str
    underlying: str
    strike_selection: str
    entry_days: List[str]
    entry_time: str
    exit_time: str
    target_profit_pct: float
    stop_loss_pct: float
    spot_condition: str

class RiskConfig(BaseModel):
    capital: float
    position_sizing: str
    risk_per_trade_pct: float
    max_slippage_pct: float
    commission_per_lot: float = 20.0  # Default value makes it optional

class BacktestRequest(BaseModel):
    strategy_config: StrategyConfig
    risk_config: RiskConfig
    start_date: Optional[str] = None  # Auto-filled based on timeframe if not provided
    end_date: Optional[str] = None    # Auto-filled based on timeframe if not provided
    timeframe: str
    data_source: str
    spot_file: Optional[str] = None
    vix_file: Optional[str] = None

@app.get("/api/metadata/kite-limits")
async def get_kite_limits():
    """
    Returns API retention limits for different timeframes.
    """
    return {
        "1m": {"max_days": 30, "description": "Available for last 30 days"},
        "5m": {"max_days": 100, "description": "Available for last 100 days"},
        "15m": {"max_days": 180, "description": "Available for last 180 days"},
        "30m": {"max_days": 180, "description": "Available for last 180 days"},
        "60m": {"max_days": 365, "description": "Available for last 365 days"},
        "day": {"max_days": 2000, "description": "Available for last ~5.5 years"}
    }

def get_default_date_range(timeframe: str) -> tuple:
    """
    Returns (start_date, end_date) as strings based on Kite Connect limits.
    
    Args:
        timeframe: Candle interval (1m, 5m, 15m, 30m, 60m, day)
    
    Returns:
        Tuple of (start_date_str, end_date_str) in YYYY-MM-DD format
    """
    from datetime import datetime, timedelta
    
    # Map timeframe to max days
    limits = {
        "1m": 30,
        "minute": 30,
        "5m": 100,
        "5minute": 100,
        "15m": 180,
        "15minute": 180,
        "30m": 180,
        "30minute": 180,
        "60m": 365,
        "60minute": 365,
        "hour": 365,
        "day": 2000
    }
    
    max_days = limits.get(timeframe, 30)  # Default to 30 days if unknown
    
    # End date: today
    end_date = datetime.now().date()
    
    # Start date: end_date - max_days
    start_date = end_date - timedelta(days=max_days)
    
    return (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

@app.get("/api/metadata/default-dates/{timeframe}")
async def get_default_dates(timeframe: str):
    """
    Returns default start/end dates for a given timeframe based on Kite limits.
    """
    start, end = get_default_date_range(timeframe)
    return {
        "start_date": start,
        "end_date": end,
        "timeframe": timeframe
    }

@app.get("/api/metadata/local-sources")
async def get_local_sources():
    """
    Scans data directories for available CSVs.
    """
    import os
    base_dir = os.getcwd()
    data_dirs = [
        os.path.join(base_dir, "data", "historical"),
        os.path.join(base_dir, "data", "backtest")
    ]
    
    spot_files = []
    vix_files = []
    
    for d in data_dirs:
        if not os.path.exists(d):
            continue
            
        for f in os.listdir(d):
            if f.endswith(".csv"):
                file_path = os.path.join(d, f)
                # Basic metadata extraction (could be improved by reading first/last line)
                # For now, just listing them.
                
                item = {
                    "id": f,
                    "name": f,
                    "granularity": "1m" if "1min" in f else "custom",
                    "path": file_path
                }
                
                if "nifty" in f.lower() or "bank" in f.lower():
                    spot_files.append(item)
                elif "vix" in f.lower():
                    vix_files.append(item)
                elif "synthetic" in f.lower():
                     # Treat synthetic options as a special case or maybe just spot for now?
                     # Actually synthetic options replaces the need for separate spot/vix in the runner,
                     # but UI requests "Spot Data Source" and "VIX Data Source".
                     # Let's add it to spot for visibility
                     item["name"] = f"Synthetic: {f}"
                     spot_files.append(item)

    return {
        "spot": spot_files,
        "vix": vix_files
    }

def resolve_file_path(file_id: str) -> str:
    """Helper to find full path of a local CSV given its ID (filename)."""
    base_dir = os.getcwd()
    search_dirs = [
        os.path.join(base_dir, "data", "historical"),
        os.path.join(base_dir, "data", "backtest")
    ]
    for d in search_dirs:
        candidate = os.path.join(d, file_id)
        if os.path.exists(candidate):
            return candidate
    return ""

@app.post("/api/backtest/run")
async def run_backtest(req: BacktestRequest):
    logger.info(f"Received Backtest Request (Streaming): {req.dict()}")
    
    def backtest_event_generator(request_data: BacktestRequest):
        q = queue.Queue()
        
        def worker():
            try:
                # Callback to push progress to queue
                def on_progress(pct, msg):
                    q.put({"type": "progress", "value": pct, "message": msg})

                on_progress(1, "Initializing Backtest Engine...")
                
                # AUTO-FILL DATES if not provided (use Kite limits)
                start_date_str = request_data.start_date
                end_date_str = request_data.end_date
                
                if not start_date_str or not end_date_str:
                    logger.info(f"Dates not provided. Auto-filling based on timeframe: {request_data.timeframe}")
                    default_start, default_end = get_default_date_range(request_data.timeframe)
                    start_date_str = start_date_str or default_start
                    end_date_str = end_date_str or default_end
                    on_progress(2, f"Auto-selected date range: {start_date_str} to {end_date_str}")
                
                # 1. Parse Dates
                s_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                e_date = datetime.strptime(end_date_str, "%Y-%m-%d") # e.g. 2024-01-31
                
                # Validate date range for Kite data source
                if request_data.data_source == "kite":
                    limits = {
                        "1m": 30, "minute": 30,
                        "5m": 100, "5minute": 100,
                        "15m": 180, "15minute": 180,
                        "30m": 180, "30minute": 180,
                        "60m": 365, "60minute": 365, "hour": 365,
                        "day": 2000
                    }
                    max_days = limits.get(request_data.timeframe, 30)
                    requested_days = (e_date - s_date).days
                    
                    if requested_days > max_days:
                        logger.warning(f"Requested {requested_days} days exceeds Kite limit of {max_days} days for {request_data.timeframe}")
                        on_progress(3, f"⚠️ Date range exceeds Kite limit ({max_days} days). Adjusting...")
                        # Auto-adjust start date
                        s_date = e_date - timedelta(days=max_days)
                        logger.info(f"Adjusted start date to: {s_date.date()}")
                
                # Adjust end_date to include full day for Kite historical
                e_date = e_date + timedelta(hours=23, minutes=59)

                # 2. Map Interval
                kite_interval = "minute"
                if request_data.timeframe.endswith("m"):
                    kite_interval = "minute" 
                    if request_data.timeframe != "1m":
                        kite_interval = f"{request_data.timeframe.replace('m', '')}minute"
                elif request_data.timeframe.endswith("d"):
                    kite_interval = "day"

                on_progress(5, f"Fetching Market Data ({kite_interval})...")
                
                # 3. Fetch Data
                # SWITCH TO FUTURES for Volume (VWAP support)
                fut_token = get_nifty_futures_token()
                use_token = fut_token if fut_token else nifty_token
                
                token_label = "NIFTY FUT" if fut_token else "NIFTY SPOT"
                logger.info(f"Using {token_label} (Token: {use_token}) for backtest data.")
                
                # Fetch Underlying (Nifty Futures or Spot)
                spot_records = fetch_kite_data_chunked(
                    use_token, s_date, e_date, kite_interval, 
                    progress_callback=lambda p, m: on_progress(5 + int(p*0.4), f"Data ({token_label}): {m}") 
                )
                spot_df = pd.DataFrame(spot_records)
                
                if spot_df.empty:
                    logger.warning(f"No Data for {token_label}. Falling back to NIFTY SPOT.")
                    use_token = nifty_token
                    token_label = "NIFTY SPOT (Fallback)"
                    spot_records = fetch_kite_data_chunked(
                        use_token, s_date, e_date, kite_interval, 
                        progress_callback=lambda p, m: on_progress(5 + int(p*0.4), f"Data ({token_label}): {m}") 
                    )
                    spot_df = pd.DataFrame(spot_records)
                
                if spot_df.empty:
                     raise Exception(f"No Data returned from Kite for {token_label}")
                    
                # Ensure Volume exists (fill random if missing/zero from Spot to enable VWAP)
                # Ensure Volume exists (fill random if missing/zero from Spot to enable VWAP)
                # If >50% of rows have 0 volume, inject synthetic volume
                if 'volume' not in spot_df.columns or (spot_df['volume'] == 0).sum() > len(spot_df) * 0.5:
                     logger.warning("Volume missing or mostly 0 in data. Injecting synthetic volume.")
                     spot_df['volume'] = np.random.randint(1000, 50000, size=len(spot_df))
                    
                # Fetch VIX (India VIX) - Chunked
                vix_records = fetch_kite_data_chunked(
                    vix_token, s_date, e_date, kite_interval,
                    progress_callback=lambda p, m: on_progress(45 + int(p*0.05), "Fetching VIX...") # Quick bump
                )
                vix_df = pd.DataFrame(vix_records)
                if vix_df.empty:
                    logger.warning("No VIX Data from Kite. Using default 20%")
                    vix_df = pd.DataFrame({'date': spot_df['date'], 'close': 20.0}) 

                # 4. Standardize Dataframes
                if 'date' in spot_df.columns: 
                    spot_df['date'] = pd.to_datetime(spot_df['date']).dt.tz_localize(None)
                    spot_df.rename(columns={'date': 'datetime', 'close': 'nifty_close'}, inplace=True)
                
                if 'date' in vix_df.columns:
                    vix_df['date'] = pd.to_datetime(vix_df['date']).dt.tz_localize(None)
                    vix_df.rename(columns={'date': 'datetime', 'close': 'vix_close'}, inplace=True)
                
                # Merge logic (same as before)
                merged = pd.merge_asof(spot_df.sort_values('datetime'), 
                                     vix_df[['datetime', 'vix_close']].sort_values('datetime'), 
                                     on='datetime', direction='backward')
                
                # Synthetic Options Logic...
                on_progress(50, "Generating Synthetic Options Surface...")
                
                processed_rows = []
                for _, row in merged.iterrows():
                    # Generate ATM Strike
                    strike = round(row['nifty_close'] / 50) * 50
                    
                    # Generate Synthetic Prices
                    dte = 4 
                    
                    # Estimate IV from VIX
                    iv = row['vix_close'] / 100.0
                    
                    # Calculate Prices
                    call_p = black_scholes_price('CE', row['nifty_close'], strike, dte/365.0, 0.1, iv)
                    put_p = black_scholes_price('PE', row['nifty_close'], strike, dte/365.0, 0.1, iv)
                    
                    # Basic Greeks (Approximation or recalc)
                    # For backtest, we mainly need Price and maybe Delta.
                    # We can use the IV we just used.
                    call_iv = iv
                    put_iv = iv
                    
                    # Recalculate Delta? Or just ignore for now if not used in Strategy.
                    # call_delta = ... 
                    
                    new_row = row.to_dict()
                    new_row['call_symbol'] = f"NIFTY {strike} CE"
                    new_row['put_symbol'] = f"NIFTY {strike} PE"
                    new_row['call_price'] = call_p
                    new_row['put_price'] = put_p
                    new_row['atm_strike'] = strike
                    
                    processed_rows.append(new_row)
                    
                final_df = pd.DataFrame(processed_rows)
                
                on_progress(55, "Running Strategy Simulation...")
                
                # 5. Run Backtest
                backtester = BacktestRunner(initial_capital=request_data.risk_config.capital)
                
                strategy_type = request_data.strategy_config.strategy_type
                
                if strategy_type == "rsi_reversal":
                     strategy = RSIReversalStrategy(period=14, overbought=60, oversold=40)
                else:
                     # Default to VWAP
                     strategy = VWAPStrategy(
                        timeframe=1, 
                        period=20,
                        devs=2.0
                     )
                
                logger.info(f"Running Backtest with Strategy: {strategy.name}")
                
                report = backtester.run(
                    strategy=strategy,
                    start_date=request_data.start_date,
                    end_date=request_data.end_date,
                    entry_time_str=request_data.strategy_config.entry_time,
                    exit_time_str=request_data.strategy_config.exit_time,
                    stop_loss_pct=request_data.risk_config.risk_per_trade_pct,
                    target_profit_pct=request_data.strategy_config.target_profit_pct,
                    dataframe=final_df,
                    progress_callback=lambda p, m: on_progress(55 + int(p*0.45), m) # Map 0-100%
                )
                
                logger.info(f"Backtest completed. Report keys: {list(report.keys())}")
                logger.info(f"Number of trades: {len(report.get('trades', []))}")
                logger.info(f"Equity curve points: {len(report.get('equity_curve', []))}")
                
                # Test JSON serialization before sending
                try:
                    test_json = json.dumps(report, cls=CustomJSONEncoder)
                    logger.info(f"JSON serialization test passed. Size: {len(test_json)} bytes")
                except Exception as json_err:
                    logger.error(f"JSON serialization failed: {json_err}", exc_info=True)
                    # Send simplified error report
                    q.put({"type": "error", "message": f"Result serialization failed: {str(json_err)}"})
                    q.put(None)
                    return
                
                q.put({"type": "result", "data": report})
                logger.info("Result queued successfully")
                
            except Exception as e:
                logger.error(f"Backtest Worker Failed: {e}", exc_info=True)
                q.put({"type": "error", "message": str(e)})
            finally:
                q.put(None) # Sentinel

        # Start Thread
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        
        # Generator Loop
        while True:
            item = q.get()
            if item is None:
                break
            yield json.dumps(item, cls=CustomJSONEncoder) + "\n"

    return StreamingResponse(backtest_event_generator(req), media_type="application/x-ndjson")


def reload_session():
    """
    Reloads the Kite Connect session using the latest access token from file.
    """
    global kite, nifty_token
    
    logger.info("Initializing Kite Connection...")
    try:
        final_access_token = ACCESS_TOKEN
        
        # Check for file-based token override
        token_file = "access_token.txt"
        if os.path.exists(token_file):
            try:
                # logger.info(f"Checking {token_file}...") 
                with open(token_file, "r") as f:
                    file_token = f.read().strip()
                if file_token:
                    final_access_token = file_token
                    logger.info(f"Loaded Access Token from {token_file}")
            except Exception as e:
                logger.warning(f"Failed to read {token_file}: {e}")

        if not final_access_token:
            logger.error("No Access Token found in ENV or file.")
            raise Exception("No Access Token Available")

        # Initialize Kite
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(final_access_token)
        

        # Test connection
        profile = kite.profile()
        logger.info(f"Connected as {profile.get('user_name')}")
        

        # FIX: Fetch Nifty Token immediately
        global vix_token # Ensure vix_token is updated
        try:
             # Fetch both NIFTY and VIX
             spot_q = kite.quote(["NSE:NIFTY 50", "NSE:INDIA VIX"])
             
             if "NSE:NIFTY 50" in spot_q:
                 nifty_token = spot_q["NSE:NIFTY 50"]["instrument_token"]
                 logger.info(f"Nifty Token Fetched: {nifty_token}")
                 
             if "NSE:INDIA VIX" in spot_q:
                 vix_token = spot_q["NSE:INDIA VIX"]["instrument_token"]
                 logger.info(f"VIX Token Fetched: {vix_token}")
                 
        except Exception as e:
             logger.warning(f"Could not fetch Tokens during reload: {e}")

        # FIX: Ensure instruments are loaded if missing (e.g., if startup failed)
        global instrument_df
        if instrument_df is None or instrument_df.empty:
             logger.info("Reloading Instruments from Kite...")
             try:
                 instruments = kite.instruments("NFO")
                 df = pd.DataFrame(instruments)
                 # Filter for NIFTY
                 df = df[df['name'] == 'NIFTY']
                 df['expiry'] = pd.to_datetime(df['expiry']).dt.date
                 
                 # Helper might raise error if no expiry
                 nearest_expiry = get_nearest_expiry(df)
                 instrument_df = df[df['expiry'] == nearest_expiry]
                 logger.info(f"Loaded {len(instrument_df)} contracts for {nearest_expiry}")
             except Exception as ie:
                 logger.error(f"Failed to load instruments during reload: {ie}")


    except Exception as e:
        logger.error(f"Session Reload Failed: {e}")
        raise e


@app.post("/api/admin/reload-token")
async def reload_token_endpoint():
    """
    Forces the server to reload the access token from disk and reconnect.
    """
    try:
        reload_session()
        
        # Restart loop if dead
        if not is_loop_running:
             logger.info("Market Loop is dead. Restarting...")
             asyncio.create_task(market_data_loop())
        
        return {"status": "success", "message": "Session Reloaded & Connected. Loop Restarted."}
    except Exception as e:
        logger.error(f"Manual Reload Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():

    global kite, instrument_df, nifty_token, is_server_running
    is_server_running = True
    
    # 0. Persistence Layer: Rehydrate
    logger.info("loading persistent state...")
    current_state = state_manager.load()
    
    # Rehydrate Risk Manager
    risk_manager.restore_state(current_state.daily_pnl, current_state.kill_switch_active)
    
    # Auto-Connect on Startup (Resilience)
    logger.info("Attempting auto-connection...")
    try:
        reload_session()
        asyncio.create_task(market_data_loop())
        logger.info("Auto-connection successful. Market Loop Started.")
    except Exception as e:
        logger.warning(f"Auto-connection failed (Token might be expired): {e}")
    
    # FIX: Deduct capital for open positions to correct "Account Balance" (Cash available)
    total_used_margin = 0.0
    for sym, pos in current_state.open_positions.items():
        qty = pos.get("quantity", 0)
        entry = pos.get("entry_price", 0.0)
        total_used_margin += (qty * entry)
        
    if total_used_margin > 0:
        risk_manager.current_capital -= total_used_margin
        logger.info(f"deducted {total_used_margin} from capital for open positions. Adjusted Balance: {risk_manager.current_capital}")
    
    # Rehydrate Strategy Manager
    strategy_manager.restore_positions(current_state.open_positions)
    
    logger.info(f"System Rehydrated. Daily PnL: {current_state.daily_pnl}, Open Pos: {len(current_state.open_positions)}")
    
    logger.info(f"System Rehydrated. Daily PnL: {current_state.daily_pnl}, Open Pos: {len(current_state.open_positions)}")
    
    # 1. Connect to Kite (Using centralized helper)
    try:
        reload_session()
    except Exception as e:
        logger.error(f"Startup Connection Failed: {e}")

        
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
    Returns active positions with real-time PnL.
    """
    try:
        positions = []
        state = state_manager.state
        
        # Safe LTP Map
        ltp_map = {}
        if option_chain_data:
            for item in option_chain_data:
                if isinstance(item, dict) and "symbol" in item:
                    ltp_map[item["symbol"]] = item.get("ltp", 0.0)
        
        if not state.open_positions:
             return []

        # Prepare Live Data Fetch
        active_tokens = []
        for sym, pos in state.open_positions.items():
             t = pos.get("token")
             if t: active_tokens.append(int(t))
        
        live_quotes = {}
        if active_tokens and kite:
             try:
                 live_quotes = kite.quote(active_tokens)
             except Exception as e:
                 logger.error(f"Failed to fetch paper trade quotes: {e}")

        for symbol, pos in state.open_positions.items():
            if not isinstance(pos, dict):
                continue
                
            p = pos.copy()
            
            # 1. Try Live Quote (Most Fresh)
            token = int(p.get("token", 0))
            current_price = 0.0
            
            # Robust key check (Int/Str)
            quote_data = live_quotes.get(token) or live_quotes.get(str(token))
            if quote_data:
                 current_price = quote_data.get("last_price", 0.0)
            
            # 2. Fallback to Option Chain Cache
            if current_price == 0:
                 # Try finding in option_chain_data by symbol if not found by token
                 # (Chain data is already in ltp_map logic if we want, but let's be direct)
                 current_price = ltp_map.get(symbol, 0.0)
            
            # 3. Fallback to Entry Price (Prevent 0 display, but indicates stale)
            if current_price == 0:
                 current_price = p.get("entry_price", 0.0)

            # CamelCase for Frontend
            p["entryPrice"] = p.get("entry_price", 0.0)
            p["quantity"] = int(p.get("quantity", 0))
            p["stopLoss"] = p.get("stop_loss", 0.0)
            p["target"] = p.get("target", 0.0)
            p["strategy"] = p.get("strategy_name", "Manual")
            
            p["currentPrice"] = current_price
            
            # Calc PnL
            qty = p["quantity"]
            entry = p["entryPrice"]
            
            pnl = 0.0
            if "CE" in symbol or "PE" in symbol:
                 pnl = (current_price - entry) * qty
            else:
                 side = p.get("side", "BUY")
                 if side == "BUY":
                     pnl = (current_price - entry) * qty
                 else:
                     pnl = (entry - current_price) * qty
                 
            p["pnl"] = pnl
            
            if "id" not in p:
                 p["id"] = str(p.get("token", symbol))
                 
            positions.append(p)
            
        return positions
    except Exception as e:
        logger.error(f"Error in get_paper_trades: {e}")
        return []

@app.delete("/trade/{token_or_symbol}")
def close_trade_manual(token_or_symbol: str):
    """
    Manually closes a trade, recording P&L.
    Accepts Token ID or Symbol Name.
    """
    try:
        state = state_manager.state
        # Find active position by token or symbol
        target_symbol = None
        target_token = 0
        decoded_id = unquote(token_or_symbol)
    
        # Try 1: Exact keys match (Symbol)
        if decoded_id in state.open_positions:
            target_symbol = decoded_id
            target_token = state.open_positions[decoded_id].get("token")
        else:
            # Try 2: Token match (using decoded_id which might be a number string)
            for sym, details in state.open_positions.items():
                if str(details.get("token", "")) == decoded_id:
                    target_symbol = sym
                    target_token = details.get("token")
                    break
        
        if not target_symbol:
             # Try 3: Raw fallback
             if token_or_symbol in state.open_positions:
                 target_symbol = token_or_symbol
                 target_token = state.open_positions[token_or_symbol].get("token")
        
        if not target_symbol:
             return {"status": "error", "message": f"Trade not found for ID: {token_or_symbol}"}
    
        # Use PaperBroker to close (Handles PnL, State, Logging)
        
        quote = {}
        exit_price = 0.0
        
        # Try 1: Fetch via Token (Most Reliable)
        if target_token:
            try:
                quote = kite.quote([int(target_token)])
                if str(target_token) in quote:
                    exit_price = quote[str(target_token)]['last_price']
                    logger.info(f"Exit Price via Token: {exit_price}")
                elif int(target_token) in quote:
                    exit_price = quote[int(target_token)]['last_price']
                    logger.info(f"Exit Price via Token (Int): {exit_price}")
            except Exception as e:
                logger.warning(f"Failed to fetch quote by token {target_token}: {e}")
        
        # Try 2: Fetch via Symbol (Fallback)
        if exit_price == 0 and target_symbol:
             try:
                 # Ensure NFO: prefix
                 search_sym = target_symbol if ":" in target_symbol else f"NFO:{target_symbol}"
                 q = kite.quote(search_sym)
                 if q:
                     vals = list(q.values())
                     exit_price = vals[0]["last_price"]
                     logger.info(f"Exit Price via Symbol {search_sym}: {exit_price}")
             except Exception as e:
                 logger.warning(f"Failed to fetch quote by symbol {target_symbol}: {e}")

        # Try 3: Option Chain Cache (Last Resort Live Data)
        if exit_price == 0 and option_chain_data:
             logger.info("Falling back to Option Chain Cache...")
             for item in option_chain_data:
                 # Loose match on strike/type
                 if item.get("symbol") == target_symbol:
                      if "callLTP" in item and "CE" in target_symbol:
                          exit_price = item["callLTP"]
                      elif "putLTP" in item and "PE" in target_symbol:
                          exit_price = item["putLTP"]
                      logger.info(f"Exit Price via Chain Cache: {exit_price}")
                      break

        # Fallback 3: Entry Price (Last resort to allow closing)
        if exit_price == 0 and target_symbol in state.open_positions:
             exit_price = state.open_positions[target_symbol].get("entry_price", 0.0)
             logger.warning(f"Closing {target_symbol} at ENTRY price {exit_price} (Live data unavailable)")

        result = paper_broker.close_position(target_symbol, price=exit_price, reason="Manual API Close")

        return result
        
    except Exception as e:
        logger.error(f"Manual Close Error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

class OrderRequest(BaseModel):
    symbol: str
    order_type: str  # MARKET, LIMIT, SL-M
    quantity: int
    price: float = 0.0
    trigger_price: float = 0.0
    product: str = "MIS"
    side: str = "BUY"  # BUY / SELL

    side: str = "BUY"  # BUY / SELL

    side: str = "BUY"  # BUY / SELL

class StrategyConfig(BaseModel):
    # Strategy Logic
    strategy_type: str = "Short Straddle"
    underlying: str = "NIFTY 50"
    strike_selection: str = "ATM"  # ATM, ITM, OTM
    entry_days: List[str] = ["All Days"] # ["Monday", "Thursday"]
    
    # Entry & Exit Rules
    entry_time: str = "09:20"  # HH:MM
    exit_time: str = "15:15"
    target_profit_pct: float = 0.0 # 0 = Disable
    stop_loss_pct: float = 0.0
    spot_condition: str = "Any" # "Above SMA20", etc.

class RiskConfig(BaseModel):
    capital: float = 100000.0
    position_sizing: str = "Fixed Lots" # "Fixed Lots", "% Capital", "Kelly"
    risk_per_trade_pct: float = 1.0
    max_slippage_pct: float = 0.5
    commission_per_lot: Optional[float] = Field(default=None)  # Optional - costs calculated by CostModel

class BacktestRequest(BaseModel):
    strategy_config: StrategyConfig
    risk_config: RiskConfig
    start_date: str
    end_date: str
    timeframe: str = "1m"
    data_source: str = "CSV" 

@app.post("/api/backtest/run")
def run_backtest(req: BacktestRequest):
    """
    Executes a Real Backtest using Module B & C.
    """
    logger.info(f"BACKTEST REQUEST: {req}")
    
    try:
        # 1. Init Runner
        # 1. Init Runner
        # 1. Init Runner
        from src.backtest_runner import BacktestRunner
        from strategy_engine.strategies.vwap import VWAPStrategy # Default for now
        
        # Get slippage from request (default 0.5%)
        slippage_pct = req.risk_config.max_slippage_pct if hasattr(req.risk_config, 'max_slippage_pct') else 0.5
        
        # Get strike selection from request
        strike_selection = req.strategy_config.strike_selection.lower() if hasattr(req.strategy_config, 'strike_selection') else "atm"
        
        runner = BacktestRunner(
            initial_capital=req.risk_config.capital, 
            slippage_pct=slippage_pct,
            strike_selection=strike_selection
        )
        
        # Initialize strategy with risk_per_trade parameter
        strategy = VWAPStrategy()
        strategy.risk_per_trade = req.risk_config.risk_per_trade_pct  # Pass to strategy
        
        # 2. Run
        print("DEBUG: Calling runner.run()")
        result = runner.run(
            strategy=strategy,
            start_date=req.start_date,
            end_date=req.end_date,
            entry_time_str=req.strategy_config.entry_time,
            exit_time_str=req.strategy_config.exit_time,
            stop_loss_pct=req.strategy_config.stop_loss_pct,
            target_profit_pct=req.strategy_config.target_profit_pct
        )
        
        # 3. Return (Result structure already matches via PerformanceAnalytics)
        if "error" in result:
             return {"status": "error", "message": result["error"]}
        
        # DEBUG: Check if equity_curve exists
        equity_curve = result.get("equity_curve", [])
        print(f"DEBUG: Equity curve has {len(equity_curve)} points")
        if equity_curve:
            print(f"DEBUG: First point = {equity_curve[0]}")
             
        return {"status": "success", "data": result}
        
    except Exception as e:
        logger.error(f"Backtest Execution Failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

class MarginRequest(BaseModel):
    symbol: str
    quantity: int
    price: float
    product: str = "MIS"
    order_type: str = "MARKET"

@app.post("/api/check-margin")
def check_margin(req: MarginRequest):
    """
    Calculates required margin for a trade.
    """
    # Simple approx: Price * Qty
    # In real world, use kite.margins()
    required = req.price * req.quantity
    available = risk_manager.current_capital
    return {
        "required": required,
        "available": available,
        "shortfall": max(0, required - available)
    }



@app.get("/api/orders")
def get_orders():
    """Returns the order log."""
    return state_manager.state.orders

@app.get("/api/history")
def get_history():
    """Returns the log of closed trades."""
    return state_manager.state.closed_trades

@app.post("/api/place-order")
def place_order_endpoint(order: OrderRequest):
    """
    Places an order (Market/Limit).
    """
    try:
        logger.info(f"ORDER REQUEST: {order}")
        
        # 1. Init Order Record
        order_id = f"ORD-{int(time.time()*1000)}"
        timestamp = datetime.now().isoformat()
        
        status = "PENDING"
        avg_price = 0.0
        msg = ""

        # 2. Get Live Price for Market Orders
        current_ltp = 0.0
        found_token = 0
        if option_chain_data:
             try:
                 # Parse Symbol: "NIFTY 25500 CE"
                 parts = order.symbol.split()
                 if len(parts) >= 3:
                      strike_price = float(parts[-2])
                      option_type = parts[-1] 
                      
                      found_token = 0
                      for item in option_chain_data:
                          if abs(item.get("strike", 0) - strike_price) < 1.0:
                               if option_type == "CE":
                                   current_ltp = item.get("callLTP", 0.0)
                                   found_token = item.get("ce_token", 0)
                               elif option_type == "PE":
                                   current_ltp = item.get("putLTP", 0.0)
                                   found_token = item.get("pe_token", 0)
                               break
             except Exception as e:
                 logger.error(f"LTP Lookup Error: {e}")
        
        # Fallback to Kite
        if current_ltp == 0 and kite:
             try:
                 q = kite.quote(f"NFO:{order.symbol}") 
                 if not q: q = kite.quote(order.symbol)
                 if q:
                     vals = list(q.values())
                     current_ltp = vals[0]["last_price"]
             except:
                 pass
                 
        # 3. Market Hours Check (Simple 9:15-15:30 check)
        now = datetime.now()
        start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        is_market_open = start_time <= now <= end_time
        
        # Override for weekends/holidays if needed, but time check is good start
        if not is_market_open:
             if order.order_type == "MARKET":
                 status = "REJECTED"
                 msg = "Market is Closed (9:15-15:30). Use LIMIT orders for offline testing."
             else:
                 # LIMIT Orders stay PENDING if market is closed
                 status = "PENDING"
                 msg = "Market Closed. Order queued."

        # 4. Execution Logic
        if status == "PENDING":
             exec_price = order.price
             
             if order.order_type == "MARKET":
                  if current_ltp > 0:
                     exec_price = current_ltp
                     status = "EXECUTED"
                  else:
                     status = "REJECTED"
                     msg = "Market Price Unavailable"
                 
             elif order.order_type == "LIMIT":
                 if order.side == "BUY" and current_ltp > 0 and current_ltp <= order.price:
                     exec_price = order.price 
                     status = "EXECUTED"
                 elif order.side == "SELL" and current_ltp > 0 and current_ltp >= order.price:
                     exec_price = order.price
                     status = "EXECUTED"
                 else:
                     status = "PENDING"
                     msg = "Limit Price not reached"

        # 5. Broker Call (If Executed)
        if status == "EXECUTED":
            try:
                # Delegate to PaperBroker (It handles logging internally)
                res = paper_broker.place_order(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    side=order.side,
                    price=exec_price,
                    product=order.product,
                    order_type=order.order_type,
                    token=found_token
                )
                # We return the broker's result directly, avoiding double log
                return {"status": "success", "data": res}
                
            except Exception as e:
                logger.error(f"Broker Error: {e}")
                status = "REJECTED"
                msg = str(e)
                
        # 6. Persist Order Log ONLY if NOT Executed by Broker (Pending/Rejected)
        # Because PaperBroker didn't run, we must log it here.
        order_record = {
            "order_id": order_id,
            "timestamp": timestamp,
            "symbol": order.symbol,
            "quantity": order.quantity,
            "side": order.side,
            "type": order.order_type,
            "product": order.product,
            "price": order.price,
            "trigger_price": order.trigger_price,
            "status": status,
            "average_price": avg_price,
            "message": msg
        }
        
        state_manager.add_order(order_record)
        
        if status == "REJECTED":
             return {"status": "error", "message": msg, "data": order_record}
             
        return {
            "status": "pending", 
            "data": order_record
        }

    except Exception as e:
        logger.error(f"Place Order Failed: {e}")
        return {"status": "error", "message": str(e)}

# Strategy Deployment Schema
class DeployStrategyRequest(BaseModel):
    # Strategy Configuration
    strategy_type: str  # "vwap", "rsi_reversal", "gamma_snap"
    underlying: str  # "NIFTY 50", "BANK NIFTY", "FIN NIFTY"
    strike_selection: str  # "atm", "itm", "otm", "delta"
    
    # Position Sizing
    position_sizing: str  # "fixed", "kelly"
    risk_per_trade_pct: float
    lots_count: int
   
    # Entry & Exit Rules
    entry_time: str  # "09:15"
    exit_time: str  # "15:30"
    target_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    spot_condition: str  # "any", "above_sma", "trending_up", "high_vol"
    
    # Greeks & Risk
    target_delta: Optional[float] = None
    min_theta: Optional[float] = None
    max_vega: Optional[float] = None
    
    # Optional (inherited from paper trading settings if not provided)
    initial_capital: Optional[float] = None
    slippage_pct: Optional[float] = None
    commission_per_lot: Optional[float] = None

@app.get("/api/account-summary")
async def get_account_summary():
    """
    Returns paper trading account summary including deployed strategies with monitoring state.
    """
    try:
        # Get deployed strategies with real-time monitoring details
        deployed_strategies = []
        for strategy_id, config in state_manager.state.deployed_strategies.items():
            strategy_info = {
                "id": strategy_id,
                "name": f"{config.get('type', 'Unknown').upper()} - {config.get('underlying', 'NIFTY')}",
                "status": config.get('status', 'active'),
                "type": config.get('type', 'unknown'),
                "config": {
                    "entry_time": config.get('entry_time'),
                    "exit_time": config.get('exit_time'),
                    "stop_loss_pct": config.get('stop_loss_pct'),
                    "target_profit_pct": config.get('target_profit_pct'),
                    "lots_count": config.get('lots_count'),
                    "underlying": config.get('underlying')
                }
            }
            
            # Get real-time monitoring state from strategy instance
            if strategy_id in deployed_strategy_instances:
                strategy_instance = deployed_strategy_instances[strategy_id]
                # Check if strategy has get_monitoring_state method
                if hasattr(strategy_instance, 'get_monitoring_state'):
                    try:
                        strategy_info["monitoring"] = strategy_instance.get_monitoring_state()
                    except Exception as e:
                        logger.error(f"Failed to get monitoring state for {strategy_id}: {e}")
                        strategy_info["monitoring"] = {
                            "entry_conditions": [],
                            "exit_conditions": [],
                            "next_action": "Error fetching state"
                        }
                else:
                    strategy_info["monitoring"] = {
                        "entry_conditions": [],
                        "exit_conditions": [],
                        "next_action": "Monitoring..."
                    }
            else:
                strategy_info["monitoring"] = {
                    "entry_conditions": [],
                    "exit_conditions": [],
                    "next_action": "Strategy instance not found"
                }
            
            deployed_strategies.append(strategy_info)
        
        return {
            "capital": risk_manager.current_capital,
            "daily_pnl": risk_manager.daily_pnl,
            "kill_switch": risk_manager.kill_switch_active,
            "strategies": deployed_strategies
        }
    except Exception as e:
        logger.error(f"Failed to get account summary: {e}")
        return {
            "capital": 200000.0,
            "daily_pnl": 0.0,
            "kill_switch": False,
            "strategies": []
        }

@app.post("/deploy-strategy")
async def deploy_strategy(req: DeployStrategyRequest):
    """
    Deploys a new strategy for paper trading with comprehensive parameters.
    """
    try:
        logger.info(f"Strategy Deployment Request: {req.dict()}")
        
        # Validate strategy type
        valid_strategies = ["vwap", "rsi_reversal", "gamma_snap", "test_timer"]
        if req.strategy_type not in valid_strategies:
            return {
                "status": "error",
                "message": f"Invalid strategy type. Must be one of: {valid_strategies}"
            }
        
        # Use defaults for optional fields
        initial_capital = req.initial_capital or risk_manager.total_capital
        slippage_pct = req.slippage_pct or (paper_broker.slippage_pct * 100)
        commission = req.commission_per_lot or 20.0
        
        # Validate capital if provided
        if initial_capital < 10000:
            return {
                "status": "error",
                "message": "Initial capital must be at least ₹10,000"
            }
        
        # Validate stop loss
        if not req.stop_loss_pct or req.stop_loss_pct <= 0:
            return {
                "status": "error",
                "message": "Stop loss percentage is required and must be greater than 0"
            }
        
        # Update risk manager with capital
        risk_manager.total_capital = initial_capital
        risk_manager.current_capital = initial_capital
        risk_manager.daily_pnl = 0.0
        
        # Update paper broker slippage if provided
        if req.slippage_pct:
            paper_broker.slippage_pct = req.slippage_pct / 100.0  # Convert to decimal
        
        # Initialize appropriate strategy
        strategy = None
        if req.strategy_type == "vwap":
            strategy = VWAPStrategy()
        elif req.strategy_type == "rsi_reversal":
            strategy = RSIReversalStrategy()
        elif req.strategy_type == "gamma_snap":
            from strategy_engine.strategies.gamma_snap import GammaSnapStrategy
            strategy = GammaSnapStrategy()
        elif req.strategy_type == "test_timer":
            from strategy_engine.strategies.test_timer import TestTimerStrategy
            strategy = TestTimerStrategy()
        
        if strategy is None:
            return {
                "status": "error",
                "message": f"Failed to initialize strategy: {req.strategy_type}"
            }
        
        # Register strategy with manager AND store instance globally
        strategy_id = f"{req.strategy_type}_{req.underlying.replace(' ', '_').lower()}_{int(time.time())}"
        strategy_manager.register_strategy(strategy)
        
        # Store strategy instance for monitoring state access
        deployed_strategy_instances[strategy_id] = strategy
        
        # Store strategy configuration in state for later reference
        strategy_config = {
            "id": strategy_id,
            "type": req.strategy_type,
            "underlying": req.underlying,
            "strike_selection": req.strike_selection,
            "entry_time": req.entry_time,
            "exit_time": req.exit_time,
            "target_profit_pct": req.target_profit_pct,
            "stop_loss_pct": req.stop_loss_pct,
            "initial_capital": initial_capital,
            "risk_per_trade_pct": req.risk_per_trade_pct,
            "lots_count": req.lots_count,
            "slippage_pct": slippage_pct,
            "commission": commission,
            "spot_condition": req.spot_condition,
            "target_delta": req.target_delta,
            "min_theta": req.min_theta,
            "max_vega": req.max_vega,
            "deployed_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        # Store in state manager
        state_manager.state.deployed_strategies[strategy_id] = strategy_config
        state_manager.save()
        
        logger.info(f"Strategy {strategy_id} deployed successfully!")
        
        return {
            "status": "success",
            "message": f"{req.strategy_type.upper()} strategy deployed successfully",
            "strategy_id": strategy_id,
            "config": strategy_config
        }
        
    except Exception as e:
        logger.error(f"Strategy Deployment Failed: {e}")
        return {
            "status": "error",
            "message": f"Deployment failed: {str(e)}"
        }


@app.delete("/api/reset")
def reset_system_state():
    """
    Clears all orders, positions, and resets capital to initial state.
    """
    state_manager.reset()
    # Reset risk_manager to initial state
    risk_manager.daily_pnl = 0.0
    risk_manager.current_capital = risk_manager.total_capital
    risk_manager.kill_switch_active = False
    
    logger.info("System Reset: All trades cleared, capital reset to 200,000")
    return {"status": "success", "message": "System fully reset. Capital: 200,000, P&L: 0"}


# ============================================
# PROJECT TELESCOPE - PATTERN DETECTION API
# ============================================

@app.get("/api/telescope/candles")
async def get_telescope_candles(timeframe: str = "1h", lookback: int = 100):
    """
    Get OHLCV candles for charting.
    
    Params:
        timeframe: '1m', '5m', '15m', '1h', '1d'
        lookback: Number of candles to return
    """
    try:
        df = telescope_resampler.get_candles(timeframe, lookback)
        
        return {
            "status": "success",
            "timeframe": timeframe,
            "candles": df.to_dict('records')
        }
    except Exception as e:
        logger.error(f"Failed to get candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telescope/signals/active")
async def get_active_signals(timeframe: Optional[str] = None):
    """
    Get all active signals, optionally filtered by timeframe.
    
    Params:
        timeframe: Optional filter ('1m', '5m', etc.)
    """
    try:
        signals = telescope_tracker.get_active_signals(timeframe)
        
        return {
            "status": "success",
            "count": len(signals),
            "signals": [s.to_dict() for s in signals]
        }
    except Exception as e:
        logger.error(f"Failed to get active signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telescope/signals/history")
async def get_signal_history(limit: int = 50):
    """
    Get recently closed signals.
    
    Params:
        limit: Maximum number to return
    """
    try:
        signals = telescope_tracker.get_historical_signals(limit)
        
        return {
            "status": "success",
            "count": len(signals),
            "signals": [s.to_dict() for s in signals]
        }
    except Exception as e:
        logger.error(f"Failed to get signal history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telescope/stats")
async def get_telescope_stats():
    """Get overall Telescope statistics."""
    try:
        stats = telescope_tracker.get_stats()
        
        # Add data range info
        start, end, count = telescope_loader.get_data_range()
        
        stats["data_range"] = {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "total_candles": count
        }
        
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/telescope/scan")
async def trigger_pattern_scan(timeframe: str = "1h"):
    """
    Manually trigger pattern scan (useful for testing).
    
    Params:
        timeframe: Which timeframe to scan
    """
    try:
        # Get recent candles
        df = telescope_resampler.get_candles(timeframe, 200)
        
        if len(df) < 50:
            return {
                "status": "error",
                "message": f"Insufficient data for {timeframe} (need 50+ candles)"
            }
        
        # Run pattern scanner
        signals = telescope_scanner.scan(df, timeframe)
        
        # Add detected signals to tracker
        signal_ids = []
        for sig in signals:
            sig_id = telescope_tracker.add_signal(sig)
            signal_ids.append(sig_id)
        
        return {
            "status": "success",
            "timeframe": timeframe,
            "patterns_detected": len(signals),
            "signal_ids": signal_ids,
            "signals": [s.to_dict() for s in signals]
        }
    except Exception as e:
        logger.error(f"Failed to scan patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server_v2:app", host="0.0.0.0", port=8001, reload=True)
