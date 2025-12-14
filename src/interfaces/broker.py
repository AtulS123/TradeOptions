from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IVirtualBroker(ABC):
    """
    Abstract Base Class for Broker Interface.
    Enforces standard methods for Live and Paper trading.
    """

    @abstractmethod
    def authenticate(self):
        """Authenticates with the broker API."""
        pass

    @abstractmethod
    def place_order(self, symbol: str, quantity: int, side: str, 
                   product: str, order_type: str, price: float = 0.0, 
                   trigger_price: float = 0.0) -> Dict[str, Any]:
        """
        Places an order.
        Returns: Order details (Dict)
        """
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Returns current positions."""
        pass

    @abstractmethod
    def get_limits(self) -> Dict[str, float]:
        """Returns funds/limits available."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str):
        """Cancels an open order."""
        pass
