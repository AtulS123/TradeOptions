import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class PositionMonitor:
    """
    Monitors open positions for SL/Target hits.
    Runs on every market tick to check if positions should be auto-closed.
    """
    
    def __init__(self, paper_broker, state_manager):
        self.broker = paper_broker
        self.state_manager = state_manager
        self.enabled = True
    
    def check_positions(self, option_chain_data: list):
        """
        Check all open positions against current prices.
        Auto-close if SL or Target is hit.
        
        Args:
            option_chain_data: List of option chain items with LTP data
        """
        if not self.enabled or not option_chain_data:
            return
        
        # Create a copy to avoid modification during iteration
        positions = dict(self.state_manager.state.open_positions)
        
        for symbol, pos in positions.items():
            stop_loss = pos.get("stop_loss", 0)
            target = pos.get("target", 0)
            entry_side = pos.get("side", "BUY")
            
            # Skip if no SL/Target set
            if stop_loss == 0 and target == 0:
                continue
            
            # Get current LTP
            current_ltp = self._get_ltp(symbol, pos.get("token"), option_chain_data)
            if current_ltp == 0:
                logger.debug(f"Could not fetch LTP for {symbol}, skipping SL/Target check")
                continue
            
            # Check conditions based on position type
            should_close = False
            reason = ""
            
            if entry_side == "BUY":
                # Long position
                if stop_loss > 0 and current_ltp <= stop_loss:
                    should_close = True
                    reason = f"Stop Loss Hit (LTP: {current_ltp} <= SL: {stop_loss})"
                elif target > 0 and current_ltp >= target:
                    should_close = True
                    reason = f"Target Hit (LTP: {current_ltp} >= Target: {target})"
            else:
                # Short position (inverted logic)
                if stop_loss > 0 and current_ltp >= stop_loss:
                    should_close = True
                    reason = f"Stop Loss Hit (LTP: {current_ltp} >= SL: {stop_loss})"
                elif target > 0 and current_ltp <= target:
                    should_close = True
                    reason = f"Target Hit (LTP: {current_ltp} <= Target: {target})"
            
            if should_close:
                logger.info(f"Auto-closing {symbol}: {reason}")
                try:
                    self.broker.close_position(symbol, price=current_ltp, reason=reason)
                except Exception as e:
                    logger.error(f"Failed to auto-close {symbol}: {e}", exc_info=True)
    
    def _get_ltp(self, symbol: str, token: int, option_chain_data: list) -> float:
        """
        Get current LTP from option chain data.
        
        Args:
            symbol: Option symbol
            token: Instrument token
            option_chain_data: List of option chain items
            
        Returns:
            Current LTP or 0 if not found
        """
        # Try matching by symbol first
        for item in option_chain_data:
            if item.get("symbol") == symbol:
                if "CE" in symbol:
                    return item.get("callLTP", 0)
                elif "PE" in symbol:
                    return item.get("putLTP", 0)
        
        # Try matching by token if symbol didn't work
        if token:
            for item in option_chain_data:
                if item.get("ce_token") == token:
                    return item.get("callLTP", 0)
                elif item.get("pe_token") == token:
                    return item.get("putLTP", 0)
        
        return 0.0
    
    def enable(self):
        """Enable position monitoring."""
        self.enabled = True
        logger.info("Position monitoring enabled")
    
    def disable(self):
        """Disable position monitoring."""
        self.enabled = False
        logger.info("Position monitoring disabled")
