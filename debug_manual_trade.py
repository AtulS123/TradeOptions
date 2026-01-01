import requests
import json

url = "http://localhost:8000/api/place-order"
payload = {
    "symbol": "NIFTY 25650 CE",
    "quantity": 75,
    "side": "BUY",
    "product": "MIS",
    "order_type": "LIMIT",
    "price": 520.65,
    "trigger_price": 0.0,
    "ltp": 520.65
}

try:
    print(f"Sending POST to {url} with payload: {payload}")
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Request Failed: {e}")
