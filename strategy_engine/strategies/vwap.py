from .base import BaseStrategy
from datetime import datetime
import pandas as pd
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class VWAPStrategy(BaseStrategy):
    """
    VWAP Momentum Strategy (The Plugin).
    Maintains its own candles and indicators.
    """
    
    def __init__(self):
        self._name = "VWAP Momentum"
        self.candles = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        self.current_candle = None
        self.last_tick_time = None
        
        # Parameters
        self.volume_multiplier = 1.5
        
    @property
    def name(self) -> str:
        return self._name
        
    def _update_candle(self, tick: dict):
        """
        Aggregates ticks into 1-minute candles.
        """
        price = tick.get('last_price')
        volume = tick.get('volume', 0) # Note: Ticker sends cumulative volume usually, or diff? 
                                      # Assuming cumulative for now, so we need diff if we want bar volume.
                                      # Actually, standard OHLC assumes 'volume' is volume *in that minute*.
                                      # If input tick has 'last_quantity' (trade vol), we sum it.
                                      # If input tick has 'volume' (day cumulative), we take diff.
                                      # For simplicity in 'fake tick' mode: assuming tick has 'volume' as 'volume traded in this tick' or we handle cum.
                                      
        # For this implementation, let's assume 'tick' comes with a timestamp.
        # Check if new minute
        tick_time = tick.get('timestamp', datetime.now())
        
        if self.current_candle is None:
            self._start_new_candle(tick_time, price, volume, tick.get('cumulative_volume', 0))
            return False

        # Check minute boundary
        current_minute = self.current_candle['timestamp'].minute
        tick_minute = tick_time.minute
        
        if tick_minute != current_minute:
            # Finalize old candle
            self.candles = pd.concat([self.candles, pd.DataFrame([self.current_candle])], ignore_index=True)
            self._start_new_candle(tick_time, price, volume, tick.get('cumulative_volume', 0))
            return True # New candle formed
            
        # Update current candle
        self.current_candle['high'] = max(self.current_candle['high'], price)
        self.current_candle['low'] = min(self.current_candle['low'], price)
        self.current_candle['close'] = price
        
        # Volume logic: If tick gives day_cumulative_volume, we calculate diff.
        # If we are effectively creating candles from polling, 'volume' in tick might be cumulative day vol.
        # Let's rely on 'cumulative_volume' tracking.
        curr_cum_vol = tick.get('cumulative_volume', 0)
        if curr_cum_vol > 0:
            vol_diff = curr_cum_vol - self.current_candle['start_cum_vol']
            self.current_candle['volume'] = max(0, vol_diff)
        else:
             # Fallback if just 'volume' (tick vol) provided
             self.current_candle['volume'] += volume
             
        return False
        
    def _start_new_candle(self, timestamp, price, volume, cum_vol):
        self.current_candle = {
            'timestamp': timestamp,
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': 0, # Will be calculated via range or summing
            'start_cum_vol': cum_vol # To calc diff
        }

    def _calculate_indicators(self):
        """
        Updates VWAP and EMA on the candles DF.
        """
        if len(self.candles) < 20:
            return

        df = self.candles.copy()
        
        # VWAP (Intraday) - Simplified for 'since start of stream'
        # Proper VWAP resets daily. Here we just cumsum our stream for simplicity.
        price = df['close'] # Approximation
        vol = df['volume']
        
        df['cum_pairs'] = (price * vol).cumsum()
        df['cum_vol'] = vol.cumsum()
        df['vwap'] = df['cum_pairs'] / df['cum_vol']
        
        # EMA 20
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        
        # Vol SMA
        df['vol_sma_20'] = df['volume'].rolling(window=20).mean()
        
        return df.iloc[-1]

    def process_tick(self, tick_data: dict) -> Optional[dict]:
        """
        The Main Logic loop.
        """
        new_candle_formed = self._update_candle(tick_data)
        
        if not new_candle_formed:
            return None
            
        # Only run logic on candle close
        if len(self.candles) < 20:
            return None
            
        latest = self._calculate_indicators()
        
        # Logic
        price = latest['close']
        vwap = latest['vwap']
        ema = latest['ema_20']
        vol = latest['volume']
        avg_vol = latest['vol_sma_20']
        
        # Signal?
        action = None
        if price > vwap and price > ema and vol > (avg_vol * self.volume_multiplier):
            action = "BUY"
        elif price < vwap and price < ema and vol > (avg_vol * self.volume_multiplier):
            action = "SELL" # Or PE BUY
            
        if action:
            logger.info(f"VWAP Signal Detected: {action} @ {price}")
            return {
                "action": action,
                "token": tick_data.get('instrument_token'),
                "tag": "VWAP_MOMENTUM",
                "price": price
            }
            
        return None
