import logging
from typing import Dict, Optional
from .strategies.base import BaseRiskStrategy
from .strategies.kelly import KellyRiskStrategy

logger = logging.getLogger(__name__)

class RiskManager:
    """
    The Gatekeeper.
    Orchestrates risk management:
    1. Global Safety: Kill Switch (Daily Loss Limit).
    2. Trade Validation: R:R Check.
    3. Position Sizing: Delegates to active Strategy (e.g., Kelly).
    """

    def __init__(self, 
                 total_capital: float = 100000.0, 
                 max_daily_loss_pct: float = 0.05, 
                 min_risk_reward_ratio: float = 2.0,
                 risk_strategy: Optional[BaseRiskStrategy] = None):
        
        self.total_capital = total_capital
        self.current_capital = total_capital
        self.max_daily_loss_limit = -(total_capital * max_daily_loss_pct)
        self.min_risk_reward_ratio = min_risk_reward_ratio
        
        self.daily_pnl = 0.0
        self.kill_switch_active = False
        
        # Default to Kelly if no strategy provided
        self.strategy = risk_strategy if risk_strategy else KellyRiskStrategy()
        
        logger.info(f"RiskManager Initialized. Capital: {total_capital}, MaxLoss: {self.max_daily_loss_limit}, MinRR: {min_risk_reward_ratio}")

    def check_kill_switch(self) -> bool:
        """
        Halts trading if daily loss limit is hit.
        """
        if self.daily_pnl <= self.max_daily_loss_limit:
            if not self.kill_switch_active: # Log once
                logger.critical(f"KILL SWITCH TRIGGERED. Daily PnL: {self.daily_pnl} <= Limit: {self.max_daily_loss_limit}")
            self.kill_switch_active = True
            return True
            
        return False

    def validate_trade_setup(self, entry_price: float, stop_loss: float, target_price: float) -> Dict:
        """
        Refuses trades with poor Risk:Reward.
        Returns: {"approved": bool, "reason": str}
        """
        if self.check_kill_switch():
             return {"approved": False, "reason": "Kill Switch Active"}

        # 1. Sanity Checks
        risk = abs(entry_price - stop_loss)
        reward = abs(target_price - entry_price)
        
        if risk <= 0:
            return {"approved": False, "reason": "Invalid Risk (Stop Loss == Entry)"}
            
        # 2. R:R Calculation
        rr_ratio = reward / risk
        
        if rr_ratio < self.min_risk_reward_ratio:
            msg = f"R:R {rr_ratio:.2f} is below minimum {self.min_risk_reward_ratio}"
            logger.warning(f"Trade Rejected: {msg}")
            return {"approved": False, "reason": msg}
            
        return {"approved": True, "reason": "Approved"}

    def get_target_size(self, entry_price: float, stop_loss: float) -> int:
        """
        Calculates position size using the active strategy.
        """
        if self.kill_switch_active:
            return 0
            
        return self.strategy.calculate_size(
            capital=self.current_capital,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_cap_pct=0.05 # Hard 5% cap passed to strategy
        )

    def update_pnl(self, pnl: float):
        """
        Update capital and check kill switch.
        """
        self.daily_pnl += pnl
        self.current_capital += pnl
        self.check_kill_switch()

    def restore_state(self, daily_pnl: float, kill_switch_active: bool):
        """
        Restores state from persistence.
        """
        self.daily_pnl = daily_pnl
        self.current_capital = self.total_capital + daily_pnl # Assuming simplified cap model
        self.kill_switch_active = kill_switch_active
        logger.info(f"RiskManager Restored: DailyPnL={daily_pnl}, KillSwitch={kill_switch_active}")

