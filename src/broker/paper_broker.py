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
                   price: float = 0.0, trigger_price: float = 0.0,
                   stop_loss: float = 0.0, target: float = 0.0, 
                   strategy_tag: str = "MANUAL", token: int = 0) -> Dict[str, Any]:
        """
        Executes a paper trade with simulated realism and ATOMIC persistence.
        """
        # 1. Simulate Slippage
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
        timestamp = datetime.now().isoformat()
        
        logger.info(f"Simulated Fill: {quantity} {symbol} @ {round(executed_price, 2)} (Slippage: {round(slippage, 2)}, Costs: {costs})")
        
        # 3. ATOMIC PERSISTENCE (Sole Authority)
        if side == "BUY":
            # Opening a Position
            # We assume BUY = OPEN for Long Options interactions
            self.state_manager.add_position(symbol, {
                "token": token,
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": round(executed_price, 2),
                "stop_loss": stop_loss, # Persisted!
                "target": target,       # Persisted!
                "option_type": "CE" if "CE" in symbol else "PE", # Inference fallback
                "strategy_name": strategy_tag,
                "timestamp": timestamp,
                "strike": 0 # TODO: Pass strike if needed, currently inferred or irrelevant for basic pnl
            })
        
        # Note: SELL side persistence is handled via 'close_position' method usually.
        # But if 'place_order' (SELL) is called directly, we might want to handle it?
        # For now, we enforce using 'close_position' for Exits to ensure PnL calc is correct.
        # But if 'place_order' is used for SELL, it's just an execution event log.

        return {
            "order_id": order_id,
            "status": "COMPLETE",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "average_price": round(executed_price, 2),
            "slippage": round(slippage, 2),
            "costs": round(costs, 2),
            "timestamp": timestamp
        }

    def close_position(self, symbol: str, price: float = 0.0, reason: str = "Signal") -> Dict[str, Any]:
        """
        Atomically closes a position and updates State & PnL.
        """
        # 1. Fetch State
        pos = self.state_manager.state.open_positions.get(symbol)
        if not pos:
            logger.warning(f"Attempted to close non-existent position: {symbol}")
            return {"status": "error", "message": "Position not found"}

        qty = pos.get("quantity", 0)
        entry_price = pos.get("entry_price", 0.0)

        # 2. Execute via Internal Order (for costs/slippage)
        # We pass side="SELL"
        exec_result = self.place_order(
            symbol=symbol,
            quantity=qty,
            side="SELL",
            price=price
        )
        
        exit_price = exec_result["average_price"]
        exit_costs = exec_result["costs"]
        
        # 3. Calculate Realized PnL
        gross_pnl = (exit_price - entry_price) * qty
        net_pnl = gross_pnl - exit_costs
        
        # 4. Update State (Atomic)
        self.state_manager.update_pnl(net_pnl)
        self.state_manager.close_position(symbol)
        
        logger.info(f"Position Closed: {symbol} | Net PnL: {round(net_pnl, 2)} | Reason: {reason}")
        
        return {
            "status": "closed",
            "symbol": symbol,
            "exit_price": exit_price,
            "net_pnl": net_pnl,
            "reason": reason,
            "order_details": exec_result
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
