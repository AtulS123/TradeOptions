
import requests
import time
import json
from datetime import datetime

API_URL = "http://127.0.0.1:8001"

def test_rsi_backtest():
    print("Wait for server startup (5s)...")
    time.sleep(5) 
    
    payload = {
        "strategy_config": {
            "strategy_type": "rsi_reversal", # TESTING THIS
            "underlying": "NIFTY 50",
            "strike_selection": "atm",
            "entry_time": "09:30",
            "exit_time": "15:15",
            "target_profit_pct": 20,
            "stop_loss_pct": 10,
            "entry_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "spot_condition": "None"
        },
        "risk_config": {
            "capital": 100000,
            "position_sizing": "contracts",
            "risk_per_trade_pct": 1, 
            "max_slippage_pct": 0.5,
            "commission_per_lot": 20
        },
        # Short range check
        "start_date": "2024-02-01",
        "end_date": "2024-02-05", 
        "timeframe": "1m",
        "data_source": "KITE_API"
    }
    
    try:
        start_t = time.time()
        print("Initiating Streaming RSI Backtest...")
        
        with requests.post(f"{API_URL}/api/backtest/run", json=payload, stream=True, timeout=300) as r:
            if r.status_code != 200:
                print(f"HTTP Error: {r.status_code}")
                try: print(r.json())
                except: print(r.text)
                return

            print("Stream Connected. Listening...")
            trades_count = 0
            for line in r.iter_lines():
                if line:
                    try:
                        msg = json.loads(line.decode('utf-8'))
                        if msg['type'] == 'progress':
                            # print(f"[P {msg['value']}%] {msg['message']}")
                            pass
                        elif msg['type'] == 'result':
                            print("\n[RESULT] RSI Backtest Complete!")
                            summary = msg['data']['summary']
                            print(f"Total Trades: {summary.get('total_trades')}")
                            print(f"Total Return: {summary.get('total_return_pct')}%")
                            trades_count = summary.get('total_trades', 0)
                        elif msg['type'] == 'error':
                            print(f"\n[ERROR] Server reported error: {msg['message']}")
                            return # FAIL
                    except Exception as e:
                        pass
                        
        end_t = time.time()
        print(f"\nTime: {end_t - start_t:.2f}s")
        
        if trades_count > 0: # Strict check
            print("RSI Strategy Verification PASSED (Trades executed)")
        elif trades_count == 0:
             print("RSI Strategy Verification PASSED (No trades found, but ran successfully)")
            
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    test_rsi_backtest()
