
import logging
from src.backtest_runner import BacktestRunner
from strategy_engine.strategies.vwap import VWAPStrategy

# Setup Logging
logging.basicConfig(level=logging.ERROR) # Only Error to keep output clean, or INFO
logger = logging.getLogger("VERIFY")
logger.setLevel(logging.INFO)

def run_verify():
    print("Initializing Backtest Verification...")
    
    # 1. Strategy
    strategy = VWAPStrategy()
    
    # 2. Runner
    runner = BacktestRunner(initial_capital=200000.0)
    
    # 3. Run
    # Pick a date range that likely exists in synthetic_options.csv (Starts 2015-01-09)
    start = "2015-01-09"
    end = "2015-01-15"
    
    print(f"Running Backtest for {start} to {end}...")
    result = runner.run(strategy, start, end)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        summary = result["summary"]
        print("Backtest Complete!")
        print(f"Initial Capital: {summary['initial_capital']}")
        print(f"Ending Capital:  {summary['ending_capital']}")
        print(f"Net Profit:      {summary['net_profit']}")
        print(f"Total Trades:    {summary['total_trades']}")
        print(f"Equity Curve Points: {len(result['equity_curve'])}")
        
        # Check if any trades happened
        if summary['total_trades'] == 0:
            print("WARNING: No trades executed. Strategy thresholds might be too strict or data missing signals.")
        else:
            print("SUCCESS: Trades executed.")

if __name__ == "__main__":
    run_verify()
