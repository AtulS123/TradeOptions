
import uuid
from typing import Dict, Any, List
from datetime import datetime
from src.interfaces.broker import IVirtualBroker
from src.broker.cost_model import CostModel

class BacktestBroker(IVirtualBroker):
    """
    In-Memory Broker for Backtesting.
    Does NOT persist to disk/state manager.
    Fills orders immediately at the passed price.
    Includes realistic transaction costs.
    """
    def __init__(self, initial_capital: float = 100000.0, slippage_pct: float = 0.0):
        self.trades = [] # History of all executed trades
        self.active_positions = {} # symbol -> {quantity, entry_price, ...}
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.cost_model = CostModel()
        self.slippage_pct = slippage_pct  # Slippage as decimal (e.g., 0.5 for 0.5%)
        self.total_brokerage = 0.0  # Track total brokerage paid
        self.total_taxes = 0.0  # Track total taxes (STT + stamp duty + exchange + SEBI + GST)

    def authenticate(self):
        return True

    def place_order(self, symbol: str, quantity: int, side: str, 
                   product: str = "MIS", order_type: str = "MARKET", 
                   price: float = 0.0, trigger_price: float = 0.0,
                   stop_loss: float = 0.0, target: float = 0.0,
                   strategy_tag: str = "BACKTEST", timestamp: str = None) -> Dict[str, Any]:
        
        # Apply Slippage (always against us)
        slippage_multiplier = 1 + (self.slippage_pct / 100.0)
        if side == "BUY":
            executed_price = price * slippage_multiplier  # Pay more when buying
        else:  # SELL
            executed_price = price / slippage_multiplier  # Receive less when selling
            
        order_id = f"BT-{len(self.trades) + 1}"
        
        # Calculate transaction costs (get breakdown to track brokerage vs taxes)
        cost_breakdown = self.cost_model.get_breakdown(
            price=executed_price,
            quantity=quantity,
            side=side
        )
        total_costs = cost_breakdown["total"]
        
        # Track costs separately
        self.total_brokerage += cost_breakdown["brokerage"]
        self.total_taxes += (cost_breakdown["stt"] + cost_breakdown["stamp_duty"] + 
                            cost_breakdown["exchange_charges"] + cost_breakdown["sebi_fees"] + 
                            cost_breakdown["gst"])
        
        # Update Internal State
        # Record for Return
        pnl_record = 0.0

        if side == "BUY":
            # OPEN Position (Assuming Long only for options for now)
            # Deduct trade value + costs from capital
            self.capital -= (executed_price * quantity) + total_costs
            
            if symbol in self.active_positions:
                # Average up
                curr = self.active_positions[symbol]
                total_cost = (curr["entry_price"] * curr["quantity"]) + (executed_price * quantity)
                new_qty = curr["quantity"] + quantity
                avg_price = total_cost / new_qty
                
                self.active_positions[symbol].update({
                    "quantity": new_qty,
                    "entry_price": avg_price
                })
            else:
                self.active_positions[symbol] = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "entry_price": executed_price,
                    "stop_loss": stop_loss,
                    "target": target,
                    "strategy": strategy_tag
                }
                
        elif side == "SELL":
            # CLOSE Position (Partial or Full)
            if symbol in self.active_positions:
                curr = self.active_positions[symbol]
                remaining = curr["quantity"] - quantity
                
                # Realize PnL (gross - exit costs)
                gross_pnl = (executed_price - curr["entry_price"]) * quantity
                pnl = gross_pnl - total_costs
                self.capital += pnl
                pnl_record = pnl
                
                if remaining <= 0:
                    del self.active_positions[symbol]
                else:
                    self.active_positions[symbol]["quantity"] = remaining

        trade_record = {
            "timestamp": timestamp if timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": executed_price,
            "strategy": strategy_tag,
            "costs": round(total_costs, 2),
            "pnl": pnl_record if side == "SELL" else 0.0
        }
        self.trades.append(trade_record)
        
        return {
            "order_id": order_id,
            "status": "COMPLETE",
            "average_price": executed_price,
            "quantity": quantity,
            "costs": round(total_costs, 2)
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self.active_positions.values())

    def get_limits(self) -> Dict[str, float]:
        return {"cash": self.capital}

    def cancel_order(self, order_id: str):
        pass

    def get_pnl(self, symbol: str, current_ltp: float) -> float:
        """
        Calculates unrealized PnL for a specific symbol based on current_ltp.
        """
        if symbol not in self.active_positions:
            return 0.0
            
        pos = self.active_positions[symbol]
        entry = pos["entry_price"]
        qty = pos["quantity"]
        
        # Long PnL
        return (current_ltp - entry) * qty
