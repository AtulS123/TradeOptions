import logging
from enum import Enum

# Setup logger
logger = logging.getLogger(__name__)

class RegimeType(Enum):
    TRENDING = "TRENDING"
    VOLATILE = "VOLATILE"
    EXTREME_FEAR = "EXTREME_FEAR"

class RegimeManager:
    """
    Classifies Market Regime based on VIX thresholds.
    """
    
    @staticmethod
    def detect_regime(vix: float) -> RegimeType:
        """
        Detects the current market regime based on India VIX.
        
        Logic:
        - VIX < 18: TRENDING (Safe for Directional/VWAP)
        - VIX 18-35: VOLATILE (Gamma Scalping zone)
        - VIX > 35: EXTREME_FEAR (Trading Halt recommended)
        """
        regime = RegimeType.TRENDING
        
        if vix < 18:
            regime = RegimeType.TRENDING
        elif 18 <= vix <= 35:
            regime = RegimeType.VOLATILE
        else:
            regime = RegimeType.EXTREME_FEAR
            
        logger.info(f"Regime Detected: [{regime.value}] (VIX: {vix})")
        return regime
