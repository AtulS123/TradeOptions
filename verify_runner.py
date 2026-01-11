import pandas as pd
import sys
import os
sys.path.append(os.getcwd())

from src.backtest_runner import BacktestRunner
from strategy_engine.strategies.vwap import VWAPStrategy
from src.utils.synthetic import generate_synthetic_feed

def test_runner():
    print("Testing BacktestRunner with injected DF...")
    try:
        spot_df = pd.read_csv("test_spot_verify.csv")
        vix_df = pd.read_csv("test_vix_verify.csv")
        df = generate_synthetic_feed(spot_df, vix_df)
        
        runner = BacktestRunner(initial_capital=100000)
        strategy = VWAPStrategy()
        
        report = runner.run(
            strategy=strategy,
            start_date="2024-01-01",
            end_date="2024-01-01",
            entry_time_str="09:15",
            exit_time_str="15:30",
            dataframe=df
        )
        
        print("Report Status:", "error" if "error" in report else "success")
        if "error" in report:
            print("Error:", report["error"])
        else:
            print("Summary:", report.get("summary"))
            
    except Exception as e:
        print(f"Runner Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_runner()
