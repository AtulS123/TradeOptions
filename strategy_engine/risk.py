import logging
import math
from .models import TradeSignal

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Central Risk Management System.
    Acting as a gatekeeper for all trades and managing position sizing.
    """
    
    # Constants
    MIN_TARGET_POINTS = 10.0
    DELTA_MIN = 0.45
    DELTA_MAX = 0.65
    MAX_CAPITAL_RISK_PER_TRADE = 0.05 # 5% cap
    LOT_SIZE = 25 # NIFTY Lot Size

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.daily_pnl = 0.0
        # Max daily loss limit: 5% of capital (loss is negative)
        self.max_daily_loss_limit = -(initial_capital * 0.05) 
        
        logger.info(f"RiskManager Initialized. CapitalRef: {self.initial_capital}, MaxLossLimit: {self.max_daily_loss_limit}")

    def check_kill_switch(self) -> bool:
        """
        Returns True if trading should be halted (Kill Switch Active).
        """
        if self.daily_pnl <= self.max_daily_loss_limit:
            logger.critical(f"KILL SWITCH ACTIVE. Daily PnL ({self.daily_pnl}) hit limit ({self.max_daily_loss_limit})")
            return True
        return False

    def validate_signal(self, signal: TradeSignal, delta: float) -> bool:
        """
        Validates if a trade signal meets risk criteria.
        """
        # 1. Delta Filter
        if not (self.DELTA_MIN <= abs(delta) <= self.DELTA_MAX):
            logger.warning(f"Trade Rejected: Delta {delta} out of range [{self.DELTA_MIN}, {self.DELTA_MAX}]")
            return False
            
        # 2. Tax Drag / Minimal Target Check
        # Ensure we capture enough points to cover spread + slippage + STT
        points_diff = abs(signal.target - signal.entry_price)
        if points_diff < self.MIN_TARGET_POINTS:
            logger.warning(f"Trade Rejected: Target range {points_diff} too small (< {self.MIN_TARGET_POINTS} pts). Tax drag risk.")
            return False
            
        return True

    def calculate_position_size(self, signal: TradeSignal, premium: float) -> int:
        """
        Calculates position size (quantity) using Quarter-Kelly criterion.
        """
        # Input Assumptions (Hardcoded for now as per requirements)
        win_rate = 0.45  # p
        win_loss_ratio = 2.0  # b
        
        # Kelly Formula: f* = (p(b+1) - 1) / b
        kelly_fraction = (win_rate * (win_loss_ratio + 1) - 1) / win_loss_ratio
        
        # Quarter Kelly
        safe_fraction = kelly_fraction * 0.25
        
        # Hard Cap at 5%
        if safe_fraction > self.MAX_CAPITAL_RISK_PER_TRADE:
            safe_fraction = self.MAX_CAPITAL_RISK_PER_TRADE
            
        if safe_fraction <= 0:
            logger.warning("Trade Rejected: Kelly fraction is zero or negative.")
            return 0
            
        # Allocation
        trade_capital = self.current_capital * safe_fraction
        
        # Calculate Quantity
        if premium <= 0:
            return 0
            
        raw_quantity = int(trade_capital / premium)
        
        # Lot Size Constraint
        # Must be multiple of 25. Floor to nearest multiple.
        lots = raw_quantity // self.LOT_SIZE
        quantity = lots * self.LOT_SIZE
        
        if quantity < self.LOT_SIZE:
            logger.warning(f"Trade Rejected: Calculated quantity {raw_quantity} < Min Lot Size {self.LOT_SIZE}. (Capital allocated: {trade_capital:.2f})")
            return 0
            
        return quantity

    def update_pnl(self, pnl: float):
        """
        Updates PnL and Capital after a trade closes.
        """
        self.daily_pnl += pnl
        self.current_capital += pnl
        logger.info(f"PnL Updated: {pnl}. Daily PnL: {self.daily_pnl}. Capital: {self.current_capital}")
