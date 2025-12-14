import csv
import os
from datetime import datetime

class TradeLogger:
    """
    Logs all executed trades to a CSV file for post-analysis.
    """
    def __init__(self, filepath: str = "trades.csv"):
        self.filepath = filepath
        self._initialize_csv()

    def _initialize_csv(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "order_id", "symbol", "action", "quantity", 
                    "price", "slippage", "costs", "strategy_tag"
                ])

    def log_trade(self, order_id: str, symbol: str, action: str, 
                 quantity: int, price: float, slippage: float, 
                 costs: float, strategy_tag: str):
        
        with open(self.filepath, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                order_id,
                symbol,
                action,
                quantity,
                price,
                slippage,
                costs,
                strategy_tag
            ])
