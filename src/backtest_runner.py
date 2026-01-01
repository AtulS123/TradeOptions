import pandas as pd
import logging
from datetime import datetime, time
from typing import Dict, Any, List, Optional
from src.broker.backtest_broker import BacktestBroker
from strategy_engine.strategies.base import BaseStrategy
from src.analytics.performance import PerformanceAnalytics

logger = logging.getLogger(__name__)

class BacktestRunner:
    """
    Runs the simulation with strict rules for Time, Risk, and Sizing.
    """
    def __init__(self, data_path: str = "data/backtest/synthetic_options.csv", initial_capital: float = 100000.0):
        self.data_path = data_path
        self.broker = BacktestBroker(initial_capital=initial_capital)
        self.capital = initial_capital
        
    def run(self, strategy: BaseStrategy, start_date: str, end_date: str, 
            entry_time_str: str = "09:20", exit_time_str: str = "15:15",
            stop_loss_pct: float = 0, target_profit_pct: float = 0) -> Dict[str, Any]:
        """
        Executes the backtest with new filters.
        """
        logger.info(f"Starting Rule-Based Backtest: {start_date} to {end_date}")
        
        # Parse Time Filters
        try:
            entry_time = datetime.strptime(entry_time_str, "%H:%M").time()
            exit_time = datetime.strptime(exit_time_str, "%H:%M").time()
        except ValueError:
            logger.warning("Invalid time format. Using defaults 09:15-15:30")
            entry_time = time(9, 15)
            exit_time = time(15, 30)

        # 1. Load Data
        try:
            df = pd.read_csv(self.data_path)
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            # INJECT VOLUME IF MISSING (For Synthetic Loading)
            if 'volume' not in df.columns:
                import numpy as np
                logger.warning("Data missing 'volume' column. Injecting synthetic volume for backtest.")
                # Random volume between 5000 and 15000 to mimic liquidity
                df['volume'] = np.random.randint(5000, 15000, size=len(df))
                
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return {"error": str(e)}

        # 2. Filter by Date (Robust Parsing)
        try:
            s_date = pd.to_datetime(start_date)
            e_date = pd.to_datetime(end_date)
            
            # Adjust end_date to include the full day (23:59:59)
            e_date = e_date + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            
            logger.info(f"Filtering Data: {s_date} to {e_date}")
        except Exception as e:
            logger.error(f"Date Parsing Error: {e}")
            return {"error": f"Invalid Date Format: {e}"}

        mask = (df['datetime'] >= s_date) & (df['datetime'] <= e_date)
        df_subset = df.loc[mask].copy()
        
        if df_subset.empty:
            return {"error": "No data found"}
            
        equity_curve = []
        
        for index, row in df_subset.iterrows():
            timestamp = row['datetime'].to_pydatetime() # Convert Timestamp to datetime
            current_time = timestamp.time()
            
            # --- TIME FILTER LOGIC ---
            # 1. Before Entry Time: No new trades, but holding existing is OK? 
            # Usually we don't hold overnight in this simple engine.
            # We skip processing 'Entry' signals if before entry_time
            can_enter = current_time >= entry_time
            
            # 2. Exit Time Gate: Force Close ALL
            if current_time >= exit_time:
                 # Check if we have open positions
                 if self.broker.get_positions():
                     # Force Close All
                     for pos in self.broker.get_positions():
                         sym = pos['symbol']
                         # Get Exit Price (ATM Call/Put) - simplification
                         p_type = "CE" if "CE" in sym else "PE"
                         curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                         
                         self.broker.place_order(sym, pos['quantity'], "SELL", curr_price, "TIME_EXIT")
                 
                 # Record Equity and Continue (Don't process strategy signals)
                 total_equity = self.broker.capital + 0 # All closed
                 equity_curve.append({
                    "timestamp": timestamp.isoformat(),
                    "equity": total_equity,
                    "drawdown": 0
                 })
                 continue

            # --- RISK MANAGEMENT (GLOBAL SL/TP) ---
            # Check PnL of open positions
            open_positions = self.broker.get_positions()
            unrealized_pnl = 0.0
            
            for pos in open_positions:
                p_type = "CE" if "CE" in pos['symbol'] else "PE"
                curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                u_pnl = self.broker.get_pnl(pos['symbol'], curr_price)
                unrealized_pnl += u_pnl
                
                # Per Position SL (Optional, here we implemented Global Portfolio SL as requested?)
                # "Generic Risk Rules (SL/TP): ... Global Safety Net"
                
            # Calculate Global PnL % for the day/session
            # Ideally we track daily_pnl. Here we track total account pnl relative to 'capital' at start of run?
            # Or is it per trade? Request says "current PnL for open positions".
            # So if we have 5000 profit on 100k capital -> 5%.
            
            pnl_pct = (unrealized_pnl / self.broker.capital) * 100
            
            # Check Gates
            forced_exit = False
            if stop_loss_pct > 0 and pnl_pct <= -stop_loss_pct:
                 forced_exit = True
                 reason = "GLOBAL_SL"
            elif target_profit_pct > 0 and pnl_pct >= target_profit_pct:
                forced_exit = True
                reason = "GLOBAL_TP"
                if self.broker.data is not None:
                    df = self.broker.data
                    print(f"DEBUG: Processing {len(df)} rows in BacktestRunner")
                    for index, row in df.iterrows():
                        timestamp = row['datetime']
                        
                        # 3. Update Market Price
                        self.broker.update_market_price(row['call_symbol'], row['call_price'], timestamp)
                        self.broker.update_market_price(row['put_symbol'], row['put_price'], timestamp)
                        
                        # 4. Strategy Signal
                        signal = strategy.generate_signal(row)
                        
                        if signal and signal['action'] != 'HOLD':
                            print(f"DEBUG: Signal Generated: {signal}")
                            # Execute Trade Logic...se 
                 
            if forced_exit:
                for pos in open_positions:
                     p_type = "CE" if "CE" in pos['symbol'] else "PE"
                     curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                     self.broker.place_order(pos['symbol'], pos['quantity'], "SELL", curr_price, reason)
                # Skip strategy processing
                can_enter = False 


            # --- STRATEGY EXECUTION ---
            if can_enter:
                # Construct Tick
                tick_data = {
                    "last_price": row['nifty_close'],
                    "volume": 10000, 
                    "cumulative_volume": 0,
                    "timestamp": timestamp
                }
                
                signal = strategy.process_tick(tick_data)
                
                if signal and signal.get("action") == "BUY": # Simplistic: Only handling Long logic from Signal
                     # Check if already in position logic (Moved from old runner)
                     # ... (Keep existing simple logic for now, focus on wrapper)
                     
                     target_type = "CE" # Default Bullish
                     # If Strategy says SELL -> Bearish -> Buy PE
                     # Wait, previous logic: "Mapping: BUY -> Buy CE, SELL -> Buy PE"
                     # Let's stick to that.
                     
                     # Check if we should reverse?
                     # Allow simple "Only one position" mode for Phase 1
                     if not self.broker.get_positions():
                         # SIZING LOGIC
                         # "If Fixed Lots: Use user input" -> We don't have user input here yet in arg.
                         # Let's hardcode 50 for now or pass it.
                         qty = 50 
                         
                         entry_price = row['call_price']
                         symbol = f"NIFTY {row['atm_strike']} CE"
                         
                         self.broker.place_order(symbol, qty, "BUY", entry_price, "STRATEGY_ENTRY")


            # --- RECORD EQUITY ---
            # Recalculate after potential trades
            unrealized_pnl = 0.0
            for pos in self.broker.get_positions():
                 p_type = "CE" if "CE" in pos['symbol'] else "PE"
                 curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                 unrealized_pnl += self.broker.get_pnl(pos['symbol'], curr_price)
            
            total_equity = self.broker.capital + unrealized_pnl
            
            equity_curve.append({
                "timestamp": timestamp.isoformat(),
                "equity": round(total_equity, 2),
                "drawdown": 0
            })


        # 6. Force Exit at End of Period
        if self.broker.get_positions():
            print(f"DEBUG: Force Closing {len(self.broker.get_positions())} positions at end.")
            # Use last known timestamp and prices from 'row'
            # Note: 'row' variable is from loop scope. Python leaks loop variables, so 'row' is last row.
            # Safety: Check if 'row' exists (in case df was empty)
            if 'row' in locals():
                for pos in self.broker.get_positions():
                    p_type = "CE" if "CE" in pos['symbol'] else "PE"
                    curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                    self.broker.place_order(pos['symbol'], pos['quantity'], "SELL", curr_price, "FORCE_EXIT")
        
        # 7. Analytics
        report = PerformanceAnalytics.calculate_metrics(equity_curve, self.broker.trades, self.capital)
        print(f"DEBUG: BacktestRunner Returning Real Report with {len(self.broker.trades)} trades")
        return report
