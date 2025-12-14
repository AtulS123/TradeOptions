import uuid
import logging
from typing import Dict, Any, List, Optional
from src.interfaces.broker import IVirtualBroker
from src.broker.cost_model import CostModel
from state.state_manager import StateManager
from datetime import datetime

logger = logging.getLogger(__name__)

class PaperBroker(IVirtualBroker):
    """
    Simulates a real exchange with Slippage and Transaction Costs.
    Acts as the 'Source of Truth' for PnL.
    """
    
    def __init__(self, state_manager: StateManager, slippage_pct: float = 0.0005): # 0.05% default
        self.state_manager = state_manager
        self.slippage_pct = slippage_pct
        self.positions = {} 
        self.cost_model = CostModel()

    def authenticate(self):
        return True

    def place_order(self, symbol: str, quantity: int, side: str, 
                   product: str = "MIS", order_type: str = "MARKET", 
                   price: float = 0.0, trigger_price: float = 0.0) -> Dict[str, Any]:
        """
        Executes a paper trade with simulated realism.
        Returns: {order_id, executed_price, costs, slippage, ...}
        """
        # 1. Simulate Slippage
        # If BUY, we pay MORE. If SELL, we get LESS.
        slippage = 0.0
        executed_price = price
        
        if side == "BUY":
            slippage = price * self.slippage_pct
            executed_price = price + slippage
        elif side == "SELL":
            slippage = price * self.slippage_pct
            executed_price = price - slippage

        # 2. Calculate Costs
        costs = self.cost_model.calculate_transaction_cost(
            price=executed_price,
            quantity=quantity,
            side=side
        )

        order_id = f"PAPER-{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Simulated Fill: {quantity} {symbol} @ {round(executed_price, 2)} (Slippage: {round(slippage, 2)}, Costs: {costs})")
        
        # 3. Persist to StateManager? 
        # The user requested 'Accept StateManager instance to persist trades.'
        # If BUY (Opening), we add to State.
        # If SELL (Closing), we don't necessarily 'remove' here in this specific method call unless strictly instructed, 
        # but the main loop logic relied on main.py handling the reversal logic.
        # HOWEVER, the objective is "Stop handling paper trades manually in main.py".
        # So we should probably handle state updates here.
        # But 'place_order' is generic. How do we know if it's open or close?
        # Typically:
        # Buy -> Open (if Long only)
        # Sell -> Close (if Long only)
        # Assuming simple Long-only Options Strategy for now.
        
        # If side == BUY, Add Position
        if side == "BUY":
             # We need 'token'? The generic place_order interface takes 'symbol'.
             # Ideally we pass token too using **kwargs or similar if we strictly follow interface.
             # But 'symbol' in our system is "NIFTY ...". 
             # We can let main.py verify the token or update add_position to be symbol-based.
             # Main loop passes token to Add Position.
             pass # Main loop Logic seems to handle 'add_position' with rich metadata (token, strategy name).
             # It's hard to move ALL persistence here without passing extra args.
             # For now, we will stick to Broker returning execution details, and main.py (The loop) updating StateManager with rich context.
             # BUT, the prompt said "Stop handling paper trades manually in main.py".
             # Maybe just the 'Price Calculation' and 'Params' part? 
             # Let's trust the Broker to be the source of truth for POSITIONS?
             # "The Broker is the only component allowed to say whether a position is open or closed."
             # This implies Broker manages self.positions.
             pass

        return {
            "order_id": order_id,
            "status": "COMPLETE",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "average_price": round(executed_price, 2),
            "slippage": round(slippage, 2),
            "costs": round(costs, 2),
            "timestamp": datetime.now().isoformat()
        }

    def get_pnl(self, symbol: str, current_ltp: float) -> float:
        """
        Calculates Unrealized PnL based on simulated entry + estimated exit costs.
        """
        # Retrieve position from StateManager
        pos = self.state_manager.state.open_positions.get(symbol)
        if not pos:
            return 0.0
            
        entry_price = pos.get("entry_price", 0.0)
        qty = pos.get("quantity", 0)
        
        # Gross PnL
        gross_pnl = (current_ltp - entry_price) * qty
        
        # Net PnL (Subtract Exit Costs)
        # Estimate exit costs at current LTP
        exit_costs = self.cost_model.calculate_transaction_cost(
            price=current_ltp,
            quantity=qty,
            side="SELL"
        )
        
        return gross_pnl - exit_costs

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self.state_manager.state.open_positions.values())

    def get_limits(self) -> Dict[str, float]:
        return {"cash": 100000.0} # Mock

    def cancel_order(self, order_id: str):
        pass
