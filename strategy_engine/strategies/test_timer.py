"""
Test Timer Strategy - For Testing Position Management

Opens CALL positions every 2 minutes, closes after 4 minutes.
Max 2 concurrent positions.
"""

import logging
from datetime import datetime
from typing import Optional, Dict
from .base import BaseStrategy

logger = logging.getLogger(__name__)

class TestTimerStrategy(BaseStrategy):
    """
    Test strategy for verifying position management and monitoring UI.
    
    Entry: Every 2 minutes from deployment
    Exit: 4 minutes after entry per position
    Max Positions: 2 concurrent
    """
    
    def __init__(self):
        self._name = "Test Timer"
        self.last_entry_time: Optional[datetime] = None
        self.position_timers: Dict[str, datetime] = {}  # symbol -> entry_time
        self.entry_interval_seconds = 120  # 2 minutes
        self.exit_interval_seconds = 240   # 4 minutes
        self.max_positions = 2
        
    @property
    def name(self) -> str:
        return self._name
        
    def process_tick(self, tick_data: dict) -> Optional[dict]:
        """
        Process tick and return signal if entry conditions met.
        
        Returns signal dict with action="BUY" when:
        - 2 minutes elapsed since last entry
        - Position count < max_positions
        """
        now = datetime.now()
        
        # Check if we should enter a new position
        can_enter = self._should_enter(now)
        
        if can_enter:
            # Return BUY signal for ATM CALL
            logger.info(f"TestTimer: Entry signal - Positions: {len(self.position_timers)}/{self.max_positions}")
            return {
                "action": "BUY",
                "token": tick_data.get('instrument_token'),
                "tag": "TEST_TIMER",
                "price": tick_data.get('last_price', 0),
                "option_type": "CE",
                "reason": f"Timer: 2min elapsed. Positions: {len(self.position_timers)}/{self.max_positions}"
            }
        
        return None
    
    def _should_enter(self, now: datetime) -> bool:
        """Check if entry conditions are met"""
        # Check max position limit
        if len(self.position_timers) >= self.max_positions:
            return False
        
        # Check time since last entry
        if self.last_entry_time is None:
            # First entry - allow immediately
            self.last_entry_time = now
            return True
        
        elapsed = (now - self.last_entry_time).total_seconds()
        if elapsed >= self.entry_interval_seconds:
            self.last_entry_time = now
            return True
        
        return False
    
    def on_position_opened(self, symbol: str, entry_time: datetime = None):
        """Track position entry time for exit logic"""
        if entry_time is None:
            entry_time = datetime.now()
        self.position_timers[symbol] = entry_time
        logger.info(f"TestTimer: Position opened {symbol} at {entry_time}")
    
    def on_position_closed(self, symbol: str):
        """Remove position from tracking"""
        if symbol in self.position_timers:
            del self.position_timers[symbol]
            logger.info(f"TestTimer: Position closed {symbol}")
    
    def should_exit(self, symbol: str) -> tuple:
        """Check if position should be closed based on 4-minute timer"""
        if symbol not in self.position_timers:
            return False, "Position not tracked"
        
        entry_time = self.position_timers[symbol]
        elapsed = (datetime.now() - entry_time).total_seconds()
        
        if elapsed >= self.exit_interval_seconds:
            return True, f"4-minute timer expired ({int(elapsed)}s elapsed)"
        
        return False, f"Timer: {int(self.exit_interval_seconds - elapsed)}s remaining"
    
    def get_monitoring_state(self) -> dict:
        """
        Return real-time monitoring state for UI display
        """
        now = datetime.now()
        
        # Calculate next entry time
        if self.last_entry_time:
            elapsed_since_last = (now - self.last_entry_time).total_seconds()
            remaining_until_next = max(0, self.entry_interval_seconds - elapsed_since_last)
        else:
            remaining_until_next = 0  # Can enter immediately
            elapsed_since_last = 0
        
        # Build position timers for UI
        position_details = []
        for symbol, entry_time in self.position_timers.items():
            elapsed = (now - entry_time).total_seconds()
            remaining = max(0, self.exit_interval_seconds - elapsed)
            position_details.append({
                "symbol": symbol,
                "entry_time": entry_time.isoformat(),
                "elapsed_seconds": int(elapsed),
                "remaining_seconds": int(remaining),
                "will_close_in": f"{int(remaining // 60)}m {int(remaining % 60)}s"
            })
        
        return {
            "strategy_name": self._name,
            "entry_conditions": [
                {
                    "condition": "Time Interval",
                    "current": f"{int(elapsed_since_last)}s elapsed",
                    "target": f"{self.entry_interval_seconds}s (2 minutes)",
                    "status": "ready" if remaining_until_next == 0 else "waiting",
                    "next_action_in": f"{int(remaining_until_next // 60)}m {int(remaining_until_next % 60)}s" if remaining_until_next > 0 else "Ready"
                },
                {
                    "condition": "Position Limit",
                    "current": f"{len(self.position_timers)} positions",
                    "target": f"Max {self.max_positions} positions",
                    "status": "ready" if len(self.position_timers) < self.max_positions else "blocked",
                    "next_action_in": "Max reached" if len(self.position_timers) >= self.max_positions else "Available"
                }
            ],
            "exit_conditions": position_details,
            "next_entry_seconds": int(remaining_until_next),
            "position_count": len(self.position_timers),
            "max_positions": self.max_positions
        }
