import requests
import json

BASE_URL = "http://localhost:8001"

def test_reload():
    print("Testing Token Reload...")
    try:
        resp = requests.post(f"{BASE_URL}/api/admin/reload-token")
        print(f"Reload Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
    except Exception as e:
        print(f"Reload Failed: {e}")

def test_backtest():
    print("\nTesting Backtest...")
    payload = {
        "strategy_config": {
            "strategy_type": "VWAP",
            "underlying": "NIFTY 50",
            "strike_selection": "ATM",
            "entry_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "entry_time": "09:20",
            "exit_time": "15:15",
            "target_profit_pct": 0,
            "stop_loss_pct": 0,
            "spot_condition": "Any"
        },
        "risk_config": {
            "capital": 100000,
            "position_sizing": "Fixed Lots",
            "risk_per_trade_pct": 1,
            "max_slippage_pct": 0.5,
            "commission_per_lot": 20
        },
        "start_date": "2024-01-01",
        "end_date": "2024-01-02",
        "timeframe": "1m",
        "data_source": "KITE_API" # Critical: Testing API source
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/backtest/run", json=payload)
        print(f"Backtest Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                print("Backtest SUCCESS! Data received.")
                # print summary
                summary = data.get("data", {}).get("summary", {})
                print(f"Summary: {summary}")
            else:
                print(f"Backtest Logic Failed: {data.get('message')}")
        else:
            print(f"Request Failed: {resp.text}")
            
    except Exception as e:
        print(f"Backtest Connection Failed: {e}")

if __name__ == "__main__":
    test_reload()
    test_backtest()
