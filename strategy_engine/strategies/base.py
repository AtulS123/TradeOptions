from abc import ABC, abstractmethod
from typing import Optional, Dict

class BaseStrategy(ABC):
    """
    The Contract: Abstract Base Class for all strategies.
    Ensures 'Plug-and-Play' compatibility.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the strategy (e.g., 'VWAP Momentum')"""
        pass

    @abstractmethod
    def process_tick(self, tick_data: dict) -> Optional[dict]:
        """
        Process a single market tick.
        
        Args:
            tick_data: Dictionary containing tick info (price, volume, timestamp, etc.)
            
        Returns:
            Signal dictionary (e.g., {"action": "BUY", ...}) or None.
        """
        pass
