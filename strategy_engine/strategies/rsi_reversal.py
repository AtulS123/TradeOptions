from .base import BaseStrategy
from datetime import datetime
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RSIReversalStrategy(BaseStrategy):
    """
    RSI Reversal Strategy.
    Buys CALL when RSI < 20 (Oversold).
    Buys PUT when RSI > 80 (Overbought).
    """
    
    def __init__(self, period=14, overbought=60, oversold=40):
        self._name = "RSI Reversal"
        self.candles = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        self.current_candle = None
        
        # Parameters
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        
    @property
    def name(self) -> str:
        return self._name

    def seed_candles(self, historical_df: pd.DataFrame):
        """
        Hydrates with historical data.
        """
        if historical_df.empty:
            return False

        # Ensure timestamp
        if 'date' in historical_df.columns and 'timestamp' not in historical_df.columns:
            historical_df.rename(columns={'date': 'timestamp'}, inplace=True)
            
        if 'timestamp' in historical_df.columns:
            historical_df['timestamp'] = pd.to_datetime(historical_df['timestamp'])
        
        self.candles = historical_df.copy().sort_values('timestamp').reset_index(drop=True)
        
        # Calculate Indicators
        self._calculate_indicators()
        return True

    def _update_candle(self, tick: dict):
        # Same candle aggregation logic as VWAP
        price = tick.get('last_price')
        tick_time = tick.get('timestamp', datetime.now())
        
        if self.current_candle is None:
            self._start_new_candle(tick_time, price)
            return False

        if tick_time.minute != self.current_candle['timestamp'].minute:
            self.candles = pd.concat([self.candles, pd.DataFrame([self.current_candle])], ignore_index=True)
            self._start_new_candle(tick_time, price)
            return True # New candle closed
            
        # Update
        self.current_candle['high'] = max(self.current_candle['high'], price)
        self.current_candle['low'] = min(self.current_candle['low'], price)
        self.current_candle['close'] = price
        return False
        
    def _start_new_candle(self, timestamp, price):
        self.current_candle = {
            'timestamp': timestamp,
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': 0 
        }

    def _calculate_indicators(self):
        if len(self.candles) < self.period + 1:
            return None

        df = self.candles.copy()
        
        # Calculate RSI
        delta = df['close'].diff()
        
        # Wilder's Smoothing (alpha = 1/n)
        alpha = 1.0 / self.period
        
        gain = (delta.where(delta > 0, 0)).ewm(alpha=alpha, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        self.candles = df # Update state
        return df.iloc[-1]

    def process_tick(self, tick_data: dict) -> Optional[dict]:
        new_candle = self._update_candle(tick_data)
        
        if not new_candle:
            return None
        
        logger.info(f"RSI: New candle formed. Total candles: {len(self.candles)}")
            
        # Need at least period+1 candles for RSI calculation
        if len(self.candles) < self.period + 1:
            logger.info(f"RSI: Not enough candles yet. Need {self.period + 1}, have {len(self.candles)}")
            return None
            
        latest = self._calculate_indicators()
        if latest is None: 
            logger.warning("RSI: Indicator calculation returned None")
            return None
            
        rsi = latest['rsi']
        price = latest['close']
        
        logger.info(f"RSI: Current RSI={rsi:.2f}, Price={price:.2f}, Thresholds: {self.oversold}/{self.overbought}")
        
        action = None
        # Logic: 
        # RSI < 40 -> Oversold -> Buy Call (Long Underlying)
        # RSI > 60 -> Overbought -> Buy Put (Short Underlying)
        
        if rsi < self.oversold:
            action = "BUY"
        elif rsi > self.overbought:
            action = "SELL"
            
        if action:
            logger.info(f"RSI Signal: {action} @ {price} (RSI: {rsi:.2f})")
            return {
                "action": action,
                "token": tick_data.get('instrument_token'),
                "tag": "RSI_REVERSAL",
                "price": price,
                "meta": {"rsi": rsi}
            }
        else:
            logger.debug(f"RSI: No action. RSI {rsi:.2f} between {self.oversold} and {self.overbought}")
            
        return None
