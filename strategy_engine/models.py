from dataclasses import dataclass
from typing import Optional

@dataclass
class TradeSignal:
    """
    Standardized Trade Signal used across the system.
    """
    symbol: str
    strike: float
    type: str  # 'CE' or 'PE'
    entry_price: float
    stop_loss: float
    target: float
    risk_reward_ratio: float
    regime_detected: str
    quantity: int = 0
    confidence: float = 0.0

@dataclass
class MarketState:
    """
    Snapshot of the current market condition.
    """
    nifty_ltp: float
    india_vix: float
    pcr: float
    current_regime: str
    option_chain: Optional[list] = None
    candle_data: Optional[object] = None # pd.DataFrame
