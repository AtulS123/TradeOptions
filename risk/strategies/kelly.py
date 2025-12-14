from .base import BaseRiskStrategy
import logging

logger = logging.getLogger(__name__)

class KellyRiskStrategy(BaseRiskStrategy):
    """
    Implements the Kelly Criterion for position sizing.
    Features:
    - Quarter-Kelly safety dampener.
    - Hard Risk Cap (e.g., 5%).
    - Lot Size rounding.
    """

    def __init__(self, win_rate: float = 0.45, payoff_ratio: float = 2.0, lot_size: int = 25):
        self.win_rate = win_rate
        self.payoff_ratio = payoff_ratio
        self.lot_size = lot_size

    def calculate_size(self, capital: float, entry_price: float, stop_loss: float, risk_cap_pct: float, **kwargs) -> int:
        """
        Calculates size using Quarter-Kelly.
        """
        # 1. Calculate Kelly Fraction
        # f* = (p(b+1) - 1) / b
        p = kwargs.get('win_rate', self.win_rate)
        b = kwargs.get('payoff_ratio', self.payoff_ratio)

        if b <= 0:
            logger.warning("Invalid Payoff Ratio <= 0. Returning 0.")
            return 0

        kelly_fraction = (p * (b + 1) - 1) / b

        # 2. Apply Safety (Quarter Kelly)
        target_fraction = kelly_fraction / 4.0

        # 3. Apply Hard Cap
        allowed_fraction = min(target_fraction, risk_cap_pct)

        if allowed_fraction <= 0:
            logger.warning(f"Calculated Risk Fraction {allowed_fraction:.4f} <= 0. No Trade.")
            return 0

        # 4. Calculate Quantity
        risk_amount = capital * allowed_fraction
        
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            logger.warning("Invalid Risk Per Share (Entry approx Equal/Lower than SL).")
            return 0

        # Quantity = Risk Amount / Risk Per Share? 
        # Wait, Kelly fraction usually applies to *account size*, i.e. "Bet 5% of bankroll".
        # If I bet 5% of bankroll on a binary outcome, I lose that 5%.
        # In trading, "Risk" is (Entry-SL).
        # So Position Size * (Entry - SL) = Capital * KellyFraction.
        # Implies: Position Size = (Capital * KellyFraction) / (Entry - SL).
        # Correct.

        raw_quantity = int(risk_amount / risk_per_share)

        # 5. Lot Size Rounding (Floor)
        lots = raw_quantity // self.lot_size
        final_qty = lots * self.lot_size

        logger.info(f"Kelly Calc: f*={kelly_fraction:.2%}, Q-Kelly={target_fraction:.2%}, Capped={allowed_fraction:.2%}. Qty={final_qty}")

        return final_qty
