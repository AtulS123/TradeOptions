import pandas as pd
import logging
from datetime import datetime, time
from typing import Dict, Any, List, Optional, Callable
from src.broker.backtest_broker import BacktestBroker
from strategy_engine.strategies.base import BaseStrategy
from src.analytics.performance import PerformanceAnalytics

logger = logging.getLogger(__name__)

class BacktestRunner:
    """
    Runs the simulation with strict rules for Time, Risk, and Sizing.
    """
    def __init__(self, data_path: str = "data/backtest/synthetic_options.csv", 
                 initial_capital: float = 100000.0, 
                 slippage_pct: float = 0.5,
                 strike_selection: str = "atm"):
        self.data_path = data_path
        self.broker = BacktestBroker(initial_capital=initial_capital, slippage_pct=slippage_pct)
        self.capital = initial_capital
        self.strike_selection = strike_selection.lower()  # "atm", "itm", "otm"
        
    def run(self, strategy: BaseStrategy, start_date: str, end_date: str, 
            entry_time_str: str = "09:20", exit_time_str: str = "15:15",
            stop_loss_pct: float = 0, target_profit_pct: float = 0,
            dataframe: Optional[pd.DataFrame] = None,
            progress_callback: Optional[Callable[[int, str], None]] = None) -> Dict[str, Any]:
        """
        Executes the backtest. Supports custom DataFrame injection.
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
            if dataframe is not None:
                df = dataframe.copy()
                logger.info(f"Using injected DataFrame with {len(df)} rows")
            else:
                df = pd.read_csv(self.data_path)
            
            # Ensure Datetime
            if 'datetime' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['datetime']):
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
        
        # SEED STRATEGY with historical data for warm-up
        logger.info(f"Seeding strategy '{strategy.name}' with {len(df_subset)} candles")
        
        # Build seed DataFrame from available columns
        seed_df = pd.DataFrame()
        seed_df['timestamp'] = df_subset['datetime']
        
        # For synthetic options data, use nifty_close as OHLC
        if 'nifty_close' in df_subset.columns:
            seed_df['close'] = df_subset['nifty_close'].values
            seed_df['open'] = df_subset['nifty_close'].values  
            seed_df['high'] = df_subset['nifty_close'].values
            seed_df['low'] = df_subset['nifty_close'].values
            seed_df['volume'] = df_subset['volume'].values if 'volume' in df_subset.columns else 10000
        else:
            # Use actual OHLC if available
            seed_df['close'] = df_subset['close'].values
            seed_df['open'] = df_subset['open'].values if 'open' in df_subset.columns else df_subset['close'].values
            seed_df['high'] = df_subset['high'].values if 'high' in df_subset.columns else df_subset['close'].values
            seed_df['low'] = df_subset['low'].values if 'low' in df_subset.columns else df_subset['close'].values
            seed_df['volume'] = df_subset['volume'].values if 'volume' in df_subset.columns else 10000
        
        strategy_seeded = strategy.seed_candles(seed_df)
        logger.info(f"Strategy seeded: {strategy_seeded}")
            
        equity_curve = []
        total_rows = len(df_subset)
        
        for i, (index, row) in enumerate(df_subset.iterrows()):
            # Progress Update
            if progress_callback and i % 50 == 0: 
                pct = int((i / total_rows) * 100)
                # Map to 50-95% of total progress (0-50% was data fetch)
                progress_callback(50 + int(pct * 0.45), f"Simulating {row['datetime'].strftime('%Y-%m-%d %H:%M')}")

            timestamp = row['datetime'].to_pydatetime() # Convert Timestamp to datetime
            current_time = timestamp.time()
            
            # --- TIME FILTER LOGIC ---
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
                         
                         self.broker.place_order(
                             symbol=sym,
                             quantity=pos['quantity'],
                             side="SELL",
                             price=curr_price,
                             strategy_tag="TIME_EXIT",
                             timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S")
                         )
                 
                 # Record Equity and Continue (Don't process strategy signals)
                 total_equity = self.broker.capital + 0 # All closed
                 equity_curve.append({
                    "timestamp": timestamp.isoformat(),
                    "equity": total_equity,
                    "drawdown": 0
                 })
                 continue

            # --- POSITION-LEVEL SL/TARGET CHECK ---
            open_positions = self.broker.get_positions()
            
            for pos in open_positions[:]:
                p_type = "CE" if "CE" in pos['symbol'] else "PE"
                curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                entry_price = pos['entry_price']
                
                # Position P&L % (we bought option, profit when curr > entry)
                pos_pnl_pct = ((curr_price - entry_price) / entry_price) * 100
                
                # Check Position Stop Loss
                if stop_loss_pct > 0 and pos_pnl_pct <= -stop_loss_pct:
                    logger.info(f"Position SL: {pos['symbol']} P&L={pos_pnl_pct:.2f}%")
                    self.broker.place_order(
                        symbol=pos['symbol'],
                        quantity=pos['quantity'],
                        side="SELL",
                        price=curr_price,
                        strategy_tag="POSITION_SL",
                        timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    can_enter = False
                    continue
                
                # Check Position Target Profit
                if target_profit_pct > 0 and pos_pnl_pct >= target_profit_pct:
                    logger.info(f"Position TP: {pos['symbol']} P&L={pos_pnl_pct:.2f}%")
                    self.broker.place_order(
                        symbol=pos['symbol'],
                        quantity=pos['quantity'],
                        side="SELL",
                        price=curr_price,
                        strategy_tag="POSITION_TP",
                        timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    can_enter = False
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
            
            # Calculate Global PnL %
            pnl_pct = (unrealized_pnl / self.broker.capital) * 100 if self.broker.capital > 0 else 0
            
            # Check SL/TP Gates and immediately exit if triggered
            if stop_loss_pct > 0 and pnl_pct <= -stop_loss_pct:
                # Force close all positions
                for pos in open_positions:
                     p_type = "CE" if "CE" in pos['symbol'] else "PE"
                     curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                     self.broker.place_order(
                         symbol=pos['symbol'],
                         quantity=pos['quantity'],
                         side="SELL",
                         price=curr_price,
                         strategy_tag="GLOBAL_SL",
                         timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S")
                     )
                can_enter = False  # Skip strategy processing
                
            elif target_profit_pct > 0 and pnl_pct >= target_profit_pct:
                # Force close all positions
                for pos in open_positions:
                     p_type = "CE" if "CE" in pos['symbol'] else "PE"
                     curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                     self.broker.place_order(
                         symbol=pos['symbol'],
                         quantity=pos['quantity'],
                         side="SELL",
                         price=curr_price,
                         strategy_tag="GLOBAL_TP",
                         timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S")
                     )
                can_enter = False  # Skip strategy processing


            # --- STRATEGY EXECUTION ---
            if can_enter:
                # Construct Tick
                tick_data = {
                    "last_price": row['nifty_close'],
                    "volume": row.get('volume', 10000),  # Use actual volume if available
                    "cumulative_volume": 0,
                    "timestamp": timestamp
                }
                
                signal = strategy.process_tick(tick_data)
                
                if signal and signal.get("action") in ["BUY", "SELL"]:
                    # Only enter if no position (simple one-position-at-a-time logic)
                    if not self.broker.get_positions():
                        # SIGNAL-TO-ORDER TRANSLATION
                        action = signal.get("action")
                        
                        # Determine option type based on signal
                        # BUY signal -> Bullish -> Buy CE
                        # SELL signal -> Bearish -> Buy PE
                        if action == "BUY":
                            option_type = "CE"
                            entry_price = row['call_price']
                        else:  # SELL
                            option_type = "PE"
                            entry_price = row['put_price']
                        
                        # POSITION SIZING BASED ON RISK
                        # LOT SIZE: NIFTY = 65 (correct as of 2025+)
                        lot_size = 65
                        
                        # Calculate position size based on risk_per_trade
                        # Default to 1% if not provided
                        risk_pct = signal.get("risk_per_trade", 1.0)  # From strategy config
                        
                        # Risk Amount = Capital * Risk %
                        risk_amount = self.broker.capital * (risk_pct / 100)
                        
                        # Quantity = Risk Amount / Option Premium
                        # Then round to nearest lot
                        if entry_price > 0:
                            theoretical_qty = risk_amount / entry_price
                            num_lots = max(1, round(theoretical_qty / lot_size))  # Min 1 lot
                            qty = num_lots * lot_size
                        else:
                            # Fallback to 1 lot if price is invalid
                            qty = lot_size
                        
                        logger.info(f"Position Sizing: Risk={risk_pct}%, Amount=₹{risk_amount:.0f}, Price=₹{entry_price:.2f}, Lots={num_lots}, Qty={qty}")
                        
                        # STRIKE SELECTION LOGIC
                        atm_strike = int(row['atm_strike'])
                        nifty_price = row['nifty_close']
                        
                        # Determine strike based on selection
                        if self.strike_selection == "itm":
                            # ITM: Go 1-2 strikes in the money
                            # For CE: strike below CMP, For PE: strike above CMP
                            if option_type == "CE":
                                selected_strike = atm_strike - 100  # 2 strikes ITM for CE
                            else:  # PE
                                selected_strike = atm_strike + 100  # 2 strikes ITM for PE
                        elif self.strike_selection == "otm":
                            # OTM: Go 1-2 strikes out of money
                            # For CE: strike above CMP, For PE: strike below CMP
                            if option_type == "CE":
                                selected_strike = atm_strike + 100  # 2 strikes OTM for CE
                            else:  # PE
                                selected_strike = atm_strike - 100  # 2 strikes OTM for PE
                        else:  # atm (default)
                            selected_strike = atm_strike
                        
                        logger.info(f"Strike Selection: {self.strike_selection.upper()} → Strike={selected_strike} (ATM={atm_strike}, CMP={nifty_price:.2f})")
                        
                        symbol = f"NIFTY {selected_strike} {option_type}"
                        
                        self.broker.place_order(
                            symbol=symbol,
                            quantity=qty,
                            side="BUY",  # Always BUY to open (we're buying options)
                            price=entry_price,
                            strategy_tag="STRATEGY_ENTRY",
                            timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        )


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
                    self.broker.place_order(
                        symbol=pos['symbol'],
                        quantity=pos['quantity'],
                        side="SELL",
                        price=curr_price,
                        strategy_tag="FORCE_EXIT"
                    )
            
            # Record Final Equity State (Post-Exit)
            final_equity = self.broker.capital # All closed, so Capital is Equity
            equity_curve.append({
                "timestamp": timestamp.isoformat(), # Use last known timestamp
                "equity": round(final_equity, 2),
                "drawdown": 0
            })
        
        # 7. Analytics
        try:
            report = PerformanceAnalytics.calculate_metrics(
                equity_curve, 
                self.broker.trades, 
                self.capital,
                total_brokerage=self.broker.total_brokerage,
                total_taxes=self.broker.total_taxes
            )
            logger.info(f"Backtest Complete: {len(self.broker.trades)} trades, Final Capital: {self.broker.capital}")
            logger.info(f"Report Summary: {report.get('summary', {})}")
            return report
        except Exception as e:
            logger.error(f"Analytics calculation failed: {e}", exc_info=True)
            return {
                "error": f"Analytics failed: {str(e)}",
                "trades": self.broker.trades,
                "equity_curve": equity_curve
            }
