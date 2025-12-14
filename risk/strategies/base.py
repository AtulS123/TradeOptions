from abc import ABC, abstractmethod

class BaseRiskStrategy(ABC):
    """
    Interface for modular risk sizing strategies.
    Ensures any new strategy (Kelly, Martingale, Fixed) fits the system.
    """

    @abstractmethod
    def calculate_size(self, capital: float, entry_price: float, stop_loss: float, risk_cap_pct: float, **kwargs) -> int:
        """
        Calculate the position size (quantity) for a trade.

        Args:
            capital: Current available capital.
            entry_price: entry price of the instrument.
            stop_loss: stop loss price of the instrument.
            risk_cap_pct: Maximum allowed risk percentage per trade (e.g., 0.05).
            **kwargs: Extra strategy-specific parameters (e.g., win_rate).

        Returns:
            int: Quantity (number of units/lots).
        """
        pass
