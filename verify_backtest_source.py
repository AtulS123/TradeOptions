import asyncio
import os
from unittest.mock import patch
import sys

# Add root to sys.path to allow imports
sys.path.append(os.getcwd())

from server_v2 import run_backtest, BacktestRequest, StrategyConfig, RiskConfig, resolve_file_path

async def test_manual_mode():
    print("Testing MANUAL mode with local CSVs...")
    
    # Mock Resolve File Path
    def mock_resolve(file_id):
        if file_id == "test_spot_verify.csv":
            return os.path.abspath("test_spot_verify.csv")
        if file_id == "test_vix_verify.csv":
            return os.path.abspath("test_vix_verify.csv")
        return ""

    with patch('server_v2.resolve_file_path', side_effect=mock_resolve):
        req = BacktestRequest(
            strategy_config=StrategyConfig(
                strategy_type="vwap",
                underlying="NIFTY 50",
                strike_selection="atm",
                entry_days=["Monday"],
                entry_time="09:15",
                exit_time="15:30",
                target_profit_pct=50,
                stop_loss_pct=25,
                spot_condition="any"
            ),
            risk_config=RiskConfig(
                capital=100000,
                position_sizing="fixed",
                risk_per_trade_pct=1.0,
                max_slippage_pct=0.5,
                commission_per_lot=20
            ),
            start_date="2024-01-01",
            end_date="2024-01-02",
            timeframe="1m",
            data_source="MANUAL",
            spot_file="test_spot_verify.csv",
            vix_file="test_vix_verify.csv"
        )
        
        try:
            result = await run_backtest(req)
            print("Result Status:", result.get("status"))
            if result.get("status") == "success":
                data = result.get("data")
                print("Backtest Summary:", data.get("summary"))
                # Check if trade stats are populated (even if empty df logic might return 0 trades, it should run)
                print("Trades:", len(data.get("trades", [])))
            else:
                print("Error Message:", result.get("message"))
                
        except Exception as e:
            print(f"Exception during test: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_manual_mode())
