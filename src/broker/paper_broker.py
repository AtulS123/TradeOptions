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
    
    def __init__(self, state_manager: StateManager, risk_manager: Any, slippage_pct: float = 0.0005): # 0.05% default
        self.state_manager = state_manager
        self.risk_manager = risk_manager
        self.slippage_pct = slippage_pct
        self.positions = {} 
        self.cost_model = CostModel()

    def _parse_symbol(self, symbol: str) -> dict:
        """
        Parse option symbol to extract strike and type.
        Formats supported: NIFTY26350PE, NIFTY 26350 PE, BANKNIFTY52000CE
        """
        import re
        # Remove spaces and extract
        clean = symbol.replace(" ", "")
        match = re.search(r'(\d+)(CE|PE)', clean)
        
        if match:
            return {
                "strike": int(match.group(1)),
                "option_type": match.group(2)
            }
        return {"strike": 0, "option_type": "OPT"}

    def authenticate(self):
        return True

    def place_order(self, symbol: str, quantity: int, side: str, 
                   product: str = "MIS", order_type: str = "MARKET", 
                   price: float = 0.0, trigger_price: float = 0.0,
                   stop_loss: float = 0.0, target: float = 0.0, 
                   strategy_tag: str = "MANUAL", token: int = 0) -> Dict[str, Any]:
        """
        Executes a paper trade with simulated realism and ATOMIC persistence.
        Supports MARKET, LIMIT, SL, SL-M orders.
        """
        # ===== VALIDATION LAYER =====
        validation_errors = []
        
        # 1. Quantity validation
        if quantity <= 0:
            validation_errors.append("Quantity must be positive")
        
        # 2. Symbol validation
        if not symbol or len(symbol) < 3:
            validation_errors.append("Invalid symbol")
        
        # 3. Side validation
        if side not in ["BUY", "SELL"]:
            validation_errors.append("Side must be BUY or SELL")
        
        # 4. Order type validation
        if order_type not in ["MARKET", "LIMIT", "SL", "SL-M"]:
            validation_errors.append("Invalid order type")
        
        # 5. Price validation
        if order_type in ["MARKET", "LIMIT", "SL"] and price <= 0:
            validation_errors.append(f"{order_type} order requires valid price")
        
        if order_type == "SL-M" and trigger_price <= 0:
            validation_errors.append("SL-M order requires valid trigger_price")
        
        # 6. Capital check (for BUY orders)
        if side == "BUY" and price > 0:
            estimated_cost = self.cost_model.calculate_transaction_cost(price, quantity, side)
            required_capital = (price * quantity) + estimated_cost
            
            if required_capital > self.risk_manager.current_capital:
                validation_errors.append(
                    f"Insufficient capital. Required: ₹{required_capital:.2f}, "
                    f"Available: ₹{self.risk_manager.current_capital:.2f}"
                )
        
        # Return rejection if any validation failed
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            logger.error(f"Order validation failed: {error_msg}")
            return {
                "order_id": None,
                "status": "REJECTED",
                "message": error_msg,
                "symbol": symbol,
                "side": side,
                "quantity": quantity
            }
        
        # ===== EXECUTION LOGIC =====
        # 1. Simulate Slippage & Execution Price
        slippage = 0.0
        executed_price = price
        
        # LOGIC:
        # MARKET: Fill at Current LTP (passed as 'price') +/- Slippage
        # LIMIT: Fill at Limit Price (passed as 'price')
        # SL: Fill at Limit Price (passed as 'price')
        # SL-M: Fill at Trigger Price (passed as 'trigger_price')
        
        if order_type == "MARKET":
            # 'price' argument here is Current LTP
            if side == "BUY":
                slippage = price * self.slippage_pct
                executed_price = price + slippage
            elif side == "SELL":
                slippage = price * self.slippage_pct
                executed_price = price - slippage
        
        elif order_type == "SL-M":
             executed_price = trigger_price
             # Add slippage to trigger? Ideally yes, but keeping simple.
             
        else:
            # LIMIT or SL -> Fill at Limit Price
            executed_price = price

        # 2. Calculate Costs
        costs = self.cost_model.calculate_transaction_cost(
            price=executed_price,
            quantity=quantity,
            side=side
        )

        order_id = f"PAPER-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now().isoformat()
        
        logger.info(f"Simulated Fill: {quantity} {symbol} @ {round(executed_price, 2)} (Slippage: {round(slippage, 2)}, Costs: {costs})")
        
        # Capital is updated via risk_manager.update_pnl() when position closes
        # NOT during order placement to avoid double-counting
              
        # 3. ATOMIC PERSISTENCE (Sole Authority)
        if side == "BUY":
            # Check for existing position to Average Up
            existing_pos = self.state_manager.state.open_positions.get(symbol)
            
            if existing_pos:
                old_qty = existing_pos.get("quantity", 0)
                old_entry = existing_pos.get("entry_price", 0.0)
                
                new_qty = old_qty + quantity
                # Weighted Average Price
                avg_price = ((old_entry * old_qty) + (executed_price * quantity)) / new_qty
                
                # Update existing details
                details = existing_pos.copy()
                details["quantity"] = new_qty
                details["entry_price"] = round(avg_price, 2)
                details["timestamp"] = timestamp # Update timestamp to latest interaction? Or keep open time? Keeping latest.
                
                self.state_manager.add_position(symbol, details)
                logger.info(f"Averaged Up {symbol}: New Qty {new_qty} @ {avg_price}")
                
            else:
                # Opening a Position
                # Parse symbol to extract strike and option type
                parsed = self._parse_symbol(symbol)
                
                # We assume BUY = OPEN for Long Options interactions
                self.state_manager.add_position(symbol, {
                    "token": token,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "entry_price": round(executed_price, 2),
                    "stop_loss": stop_loss, 
                    "target": target,      
                    "option_type": parsed["option_type"],
                    "strategy_name": strategy_tag,
                    "timestamp": timestamp,
                    "product": product,       
                    "order_type": order_type,
                    "strike": parsed["strike"]
                })
        
        # 4. Log Order to History
        order_record = {
            "order_id": order_id,
            "timestamp": timestamp,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": round(executed_price, 2),
            "status": "EXECUTED",
            "strategy": strategy_tag,
            "slippage": round(slippage, 2),
            "costs": round(costs, 2),
            "pnl": 0.0 # Filled order has no PnL yet. Exit orders will log Realized PnL via close_position logic or separate update.
        }
        self.state_manager.add_order(order_record)
        
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
        # Determine Exit Side (Opposite of Entry)
        entry_side = pos.get("side", "BUY") # Default to BUY (Long)
        exit_side = "SELL" if entry_side == "BUY" else "BUY"
        
        exec_result = self.place_order(
            symbol=symbol,
            quantity=qty,
            side=exit_side,
            price=price
        )
        
        exit_price = exec_result["average_price"]
        exit_costs = exec_result["costs"]
        
        # 3. Calculate Realized PnL
        # Handle both LONG (BUY to open) and SHORT (SELL to open) positions
        if entry_side == "BUY":
            # Long position: profit when exit > entry
            gross_pnl = (exit_price - entry_price) * qty
        else:
            # Short position: profit when exit < entry
            gross_pnl = (entry_price - exit_price) * qty
        
        # Calculate Detailed Costs
        exit_breakdown = self.cost_model.get_breakdown(price=exit_price, quantity=qty, side=exit_side)
        entry_breakdown = self.cost_model.get_breakdown(price=entry_price, quantity=qty, side=entry_side)
        
        entry_costs = entry_breakdown["total"]
        exit_costs = exit_breakdown["total"]
        
        net_pnl = gross_pnl - exit_costs - entry_costs
        pnl_percent = (net_pnl / (entry_price * qty)) * 100 if entry_price > 0 else 0.0
        
        # Aggregate Charges for History
        total_charges = {
            "brokerage": round(entry_breakdown["brokerage"] + exit_breakdown["brokerage"], 2),
            "stt": round(entry_breakdown["stt"] + exit_breakdown["stt"], 2),
            "exchange_charges": round(entry_breakdown["exchange_charges"] + exit_breakdown["exchange_charges"], 2),
            "stamp_duty": round(entry_breakdown["stamp_duty"] + exit_breakdown["stamp_duty"], 2),
            "sebi_fees": round(entry_breakdown["sebi_fees"] + exit_breakdown["sebi_fees"], 2),
            "gst": round(entry_breakdown["gst"] + exit_breakdown["gst"], 2),
            "total": round(entry_costs + exit_costs, 2)
        }
        
        # Calculate Duration
        entry_time_str = pos.get("timestamp")
        duration_str = "0m"
        exit_time = datetime.now()
        
        if entry_time_str:
             try:
                 entry_time = datetime.fromisoformat(entry_time_str)
                 diff = exit_time - entry_time
                 total_seconds = int(diff.total_seconds())
                 hours = total_seconds // 3600
                 minutes = (total_seconds % 3600) // 60
                 duration_str = f"{hours}h {minutes}m"
             except:
                 pass
        
        # 4. Update State (Atomic)
        # Update both state_manager (persistent) and risk_manager (runtime) to keep in sync
        self.state_manager.update_pnl(net_pnl)
        self.risk_manager.update_pnl(net_pnl)
        self.state_manager.close_position(symbol)
        
        # 5. Log to Closed Trades History
        # Parse symbol for accurate strike and type
        parsed = self._parse_symbol(symbol)
        
        closed_trade = {
            "id": f"TRD-{uuid.uuid4().hex[:8]}",
            "date": exit_time.strftime("%Y-%m-%d %H:%M"),
            "symbol": symbol,
            "strike": parsed["strike"],
            "type": parsed["option_type"],
            "action": entry_side, # Original Action (BUY/SELL)
            "quantity": qty,
            "entryPrice": entry_price,
            "exitPrice": exit_price,
            "pnl": round(net_pnl, 2),
            "pnlPercent": round(pnl_percent, 2),
            "strategy": pos.get("strategy_name", "Manual"),
            "exitReason": reason,
            "duration": duration_str,
            "mode": "PAPER", # Flag for Frontend
            "charges": total_charges # Detailed Breakdown
        }
        self.state_manager.add_closed_trade(closed_trade)
        
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
        Calculates Unrealized PnL including both entry and exit costs.
        Handles both LONG (BUY) and SHORT (SELL) positions.
        """
        # Retrieve position from StateManager
        pos = self.state_manager.state.open_positions.get(symbol)
        if not pos:
            return 0.0
            
        entry_price = pos.get("entry_price", 0.0)
        qty = pos.get("quantity", 0)
        entry_side = pos.get("side", "BUY")
        
        # Calculate Gross PnL (handle both long and short)
        if entry_side == "BUY":
            # Long position: profit when price goes up
            gross_pnl = (current_ltp - entry_price) * qty
        else:
            # Short position: profit when price goes down
            gross_pnl = (entry_price - current_ltp) * qty
        
        # Calculate both entry and exit costs
        entry_breakdown = self.cost_model.get_breakdown(
            price=entry_price,
            quantity=qty,
            side=entry_side
        )
        
        exit_side = "SELL" if entry_side == "BUY" else "BUY"
        exit_breakdown = self.cost_model.get_breakdown(
            price=current_ltp,
            quantity=qty,
            side=exit_side
        )
        
        total_costs = entry_breakdown["total"] + exit_breakdown["total"]
        net_pnl = gross_pnl - total_costs
        
        return net_pnl


    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self.state_manager.state.open_positions.values())

    def get_limits(self) -> Dict[str, float]:
        return {"cash": 100000.0} # Mock

    def cancel_order(self, order_id: str):
        pass
