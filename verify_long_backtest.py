import requests
import time



API_URL = "http://127.0.0.1:8001"



def test_backtest_long_duration():
    print("Testing Long Duration Backtest (90 Days)...")
    
    # 90 Days Range (Jan 1 2024 to Mar 31 2024)
    payload = {
        "strategy_config": {
            "strategy_type": "vwap",
            "underlying": "NIFTY 50",
            "strike_selection": "atm",
            "entry_days": ["All Days"],
            "entry_time": "09:30",
            "exit_time": "15:15",
            "target_profit_pct": 50,
            "stop_loss_pct": 25,
            "spot_condition": "any"
        },
        "risk_config": {
            "capital": 100000,
            "position_sizing": "fixed",
            "risk_per_trade_pct": 1.0,
            "max_slippage_pct": 0.5,
            "commission_per_lot": 20
        },
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "timeframe": "1m",
        "data_source": "KITE_API"
    }
    
    import json
    try:
        start_t = time.time()
        print("Initiating Streaming Request...")
        
        with requests.post(f"{API_URL}/api/backtest/run", json=payload, stream=True, timeout=300) as r:
            if r.status_code != 200:
                print(f"HTTP Error: {r.status_code}")
                print(r.text)
                return

            print("Stream Connected. Listening for events...")
            for line in r.iter_lines():
                if line:
                    try:
                        msg = json.loads(line.decode('utf-8'))
                        if msg['type'] == 'progress':
                            print(f"[PROGRESS {msg['value']}%] {msg['message']}")
                        elif msg['type'] == 'result':
                            print("\n[RESULT] Backtest Complete!")
                            summary = msg['data']['summary']
                            print(f"Total Trades: {summary.get('total_trades')}")
                            print(f"Total Return: {summary.get('total_return_pct')}%")
                        elif msg['type'] == 'error':
                            print(f"\n[ERROR] Server reported error: {msg['message']}")
                    except Exception as e:
                        print(f"Parse Error: {e} - Line: {line}")
                        
        end_t = time.time()
        print(f"\nTotal Time: {end_t - start_t:.2f} seconds")
            
    except requests.exceptions.Timeout:
         print("Backtest Timed Out (Client Side)")
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    # Wait for server to be up
    print("Waiting for server...")
    time.sleep(5)
    test_backtest_long_duration()
