
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.broker.backtest_broker import BacktestBroker
from strategy_engine.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

class BacktestRunner:
    """
    Runs the simulation by iterating over historical data,
    feeding it to the strategy, and executing trades on the BacktestBroker.
    """
    def __init__(self, data_path: str = "data/backtest/synthetic_options.csv", initial_capital: float = 100000.0):
        self.data_path = data_path
        self.broker = BacktestBroker(initial_capital=initial_capital)
        self.capital = initial_capital
        
    def run(self, strategy: BaseStrategy, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Executes the backtest.
        start_date, end_date: Format 'YYYY-MM-DD'
        """
        logger.info(f"Starting Backtest: {start_date} to {end_date} with {strategy.name}")
        
        # 1. Load Data
        try:
            df = pd.read_csv(self.data_path)
            df['datetime'] = pd.to_datetime(df['datetime'])
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return {"error": str(e)}

        # 2. Filter by Date
        mask = (df['datetime'] >= start_date) & (df['datetime'] <= end_date)
        df_subset = df.loc[mask].copy()
        
        if df_subset.empty:
            logger.warning("No data found for the given date range.")
            return {"error": "No data found"}
            
        # 3. Simulation Loop
        equity_curve = []
        cumulative_volume_mock = 0
        
        # We need to manage strategy state (candles). 
        # Ideally, we should clear strategy state before run?
        # Strategy instances might be reused, so assuming caller handles or we reset if valid.
        # VWAPStrategy -> self.candles = ...
        # If strategy has 'reset' method, call it. It implies 'seed_candles' clears it usually.
        # We will iterate row by row.
        
        for index, row in df_subset.iterrows():
            timestamp = row['datetime']
            nifty_price = row['nifty_close']
            
            # Mock Volume (Constant to make VWAP behave like SMA, ensuring no ZeroDivisionError)
            tick_vol = 10000 
            # cumulative_volume_mock += tick_vol # DISABLED: To force additive fallback in Strategy
            
            # Construct Tick Data
            tick_data = {
                "instrument_token": 256265, # NSE:NIFTY 50 Token (approx)
                "last_price": nifty_price,
                "volume": tick_vol, 
                "cumulative_volume": 0, # FORCE FALLBACK in VWAPStrategy
                "timestamp": timestamp
            }
            
            # 4. Strategy Process
            signal = strategy.process_tick(tick_data)
            
            # 5. Execution Logic
            if signal:
                action = signal.get("action")
                # Mapping: BUY -> Buy CE (Bullish), SELL -> Buy PE (Bearish)
                # Note: 'SELL' in VWAP Usually means 'Short the Asset'.
                # In Options World -> Buy Put.
                
                # Close opposites first (Stop & Reverse)
                target_type = "CE" if action == "BUY" else "PE"
                opposing_type = "PE" if target_type == "CE" else "CE"
                
                # Check active positions
                current_positions = self.broker.get_positions()
                for pos in current_positions:
                    # Check if pos is opposing
                    # Our Broker stores 'symbol'. We need to know type.
                    # We'll infer from symbol or strategy tag.
                    sym = pos['symbol']
                    if opposing_type in sym:
                         # Close it
                         # Price? We need the price of the OPTION.
                         # synthetic_options.csv has 'call_price', 'put_price' for ATM.
                         # We assume we are holding ATM.
                         exit_price = row['call_price'] if opposing_type == "CE" else row['put_price']
                         self.broker.place_order(sym, quantity=pos['quantity'], side="SELL", price=exit_price, strategy_tag="REVERSAL")
                
                # Open New Position if not already holding same direction
                already_holding = False
                for pos in self.broker.get_positions():
                    if target_type in pos['symbol']:
                        already_holding = True
                        break
                        
                if not already_holding:
                    # Buy ATM
                    # Construct generic symbol
                    strike = row['atm_strike']
                    symbol = f"NIFTY {strike} {target_type}"
                    entry_price = row['call_price'] if target_type == "CE" else row['put_price']
                    
                    # Sizing: Fixed 50 qty (1 lot legacy, now 25/75? Let's use 50)
                    qty = 50 
                    
                    self.broker.place_order(symbol, quantity=qty, side="BUY", price=entry_price, strategy_tag="VWAP")

            # 6. Mark to Market (Equity Calculation)
            # Equity = Cash + Unrealized PnL
            unrealized_pnl = 0.0
            for pos in self.broker.get_positions():
                sym = pos['symbol']
                # Infer type
                p_type = "CE" if "CE" in sym else "PE"
                curr_price = row['call_price'] if p_type == "CE" else row['put_price']
                
                unrealized_pnl += self.broker.get_pnl(sym, curr_price)
                
            total_equity = self.broker.capital + unrealized_pnl
            
            # Record Equity Curve
            equity_curve.append({
                "timestamp": timestamp.isoformat(),
                "equity": round(total_equity, 2),
                "drawdown": 0 # TODO: Calculate DD
            })

        # Summary Metrics
        wins = 0
        losses = 0
        total_pnl = self.broker.capital - self.broker.initial_capital
        
        # Analyze trades history (Closed trades PnL is in capital change)
        # We can also iterate self.broker.trades to calculate win rate more accurately
        # But broker.trades is a log. active_positions handling in broker applies PnL to capital on CLOSE.
        
        # Calculate Win Rate from Capital changes? No, unsafe.
        # Let's verify trades list? Broker stores executed LIST.
        # Does broker store PnL per trade? "place_order" returns dict, but doesn't store PnL in self.trades unless we structured it that way.
        # Review BacktestBroker code:
        # 'place_order' (SELL) calculates PnL and adds to capital.
        # It logs "trade_record" with price.
        # Ideally, we should store PnL in the trade record for SELLs.
        
        return {
            "summary": {
                "initial_capital": self.broker.initial_capital,
                "ending_capital": total_equity,
                "net_profit": total_equity - self.broker.initial_capital,
                "total_trades": len(self.broker.trades)
            },
            "equity_curve": equity_curve
        }
