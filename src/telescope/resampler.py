"""
Candle Resampler for Project Telescope

Converts 1-minute OHLCV candles to multiple timeframes (5m, 15m, 1h, 1d).
Emits "candle_closed" events when aggregation completes.

Key Features:
- Real-time aggregation from live 1m feed
- Preload historical data for accurate long-term indicators
- Thread-safe for concurrent access
- Efficient: Only recalculates on new ticks
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional,Callable
from dataclasses import dataclass
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class CandleEvent:
    """Event emitted when a candle closes."""
    timeframe: str
    candle: Dict  # {date, open, high, low, close, volume}
    timestamp: datetime

class CandleResampler:
    """
    Aggregates 1-minute candles into multiple timeframes in real-time.
    
    Timeframes supported: 1m, 5m, 15m, 1h, 1d
    """
    
    TIMEFRAMES = {
        '1m': 1,
        '5m': 5,
        '15m': 15,
        '1h': 60,
        '1d': 1440  # 1 day = 1440 minutes
    }
    
    def __init__(self):
        self.data: Dict[str, pd.DataFrame] = {
            '1m': pd.DataFrame(),
            '5m': pd.DataFrame(),
            '15m': pd.DataFrame(),
            '1h': pd.DataFrame(),
            '1d': pd.DataFrame()
        }
        
        # Current incomplete candles (being built)
        self.current_candles: Dict[str, Dict] = {}
        
        # Thread lock for concurrent access
        self.lock = threading.Lock()
        
        # Callbacks for candle_close events
        self.on_candle_close_callbacks: List[Callable] = []
        
        logger.info("CandleResampler initialized")
    
    def preload_historical(self, df_1m: pd.DataFrame):
        """
        Preload historical 1-minute data and resample to all timeframes.
        
        Args:
            df_1m: DataFrame with columns [date, open, high, low, close, volume]
        """
        with self.lock:
            logger.info(f"Preloading {len(df_1m)} 1-minute candles...")
            
            # Ensure date is datetime and set as index
            df_1m = df_1m.copy()
            df_1m['date'] = pd.to_datetime(df_1m['date'])
            df_1m = df_1m.set_index('date').sort_index()
            
            # Store 1m data
            self.data['1m'] = df_1m.reset_index()
            
            # Resample to other timeframes
            for tf in ['5m', '15m', '1h', '1d']:
                minutes = self.TIMEFRAMES[tf]
                
                if minutes < 1440:
                    # Intraday: resample by minutes
                    rule = f'{minutes}T'  # T = minutes
                else:
                    # Daily: resample by day
                    rule = 'D'
                
                resampled = df_1m.resample(rule).agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
                
                self.data[tf] = resampled.reset_index()
                logger.info(f"Resampled {tf}: {len(resampled)} candles")
    
    def add_tick(self, tick: Dict) -> List[CandleEvent]:
        """
        Add a 1-minute tick and update all timeframes.
        
        Args:
            tick: {date: datetime, open, high, low, close, volume}
            
        Returns:
            List of CandleEvents for timeframes where candles closed
        """
        with self.lock:
            events = []
            
            # Add to 1m data
            tick_time = tick['date']
            self.data['1m'] = pd.concat([
                self.data['1m'],
                pd.DataFrame([tick])
            ], ignore_index=True)
            
            # Emit event for 1m candle
            events.append(CandleEvent(
                timeframe='1m',
                candle=tick,
                timestamp=datetime.now()
            ))
            
            # Update higher timeframes
            for tf in ['5m', '15m', '1h', '1d']:
                event = self._update_timeframe(tf, tick_time, tick)
                if event:
                    events.append(event)
            
            return events
    
    def _update_timeframe(self, timeframe: str, tick_time: datetime, tick: Dict) -> Optional[CandleEvent]:
        """
        Update a specific timeframe with new tick data.
        
        Returns CandleEvent if a candle closed, else None.
        """
        minutes = self.TIMEFRAMES[timeframe]
        
        # Determine candle boundary
        if minutes < 1440:
            # Intraday: round down to nearest interval
            candle_start = tick_time.replace(second=0, microsecond=0)
            candle_start = candle_start.replace(minute=(candle_start.minute // minutes) * minutes)
        else:
            # Daily: start of day
            candle_start = tick_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Check if we have a current candle for this timeframe
        if timeframe not in self.current_candles:
            self.current_candles[timeframe] = {
                'date': candle_start,
                'open': tick['open'],
                'high': tick['high'],
                'low': tick['low'],
                'close': tick['close'],
                'volume': tick['volume']
            }
            return None
        
        current = self.current_candles[timeframe]
        
        # Check if tick belongs to current candle
        if current['date'] == candle_start:
            # Update current candle
            current['high'] = max(current['high'], tick['high'])
            current['low'] = min(current['low'], tick['low'])
            current['close'] = tick['close']
            current['volume'] += tick['volume']
            return None
        else:
            # Candle closed! Store it and start new one
            closed_candle = current.copy()
            
            # Add to data
            self.data[timeframe] = pd.concat([
                self.data[timeframe],
                pd.DataFrame([closed_candle])
            ], ignore_index=True)
            
            # Start new candle
            self.current_candles[timeframe] = {
                'date': candle_start,
                'open': tick['open'],
                'high': tick['high'],
                'low': tick['low'],
                'close': tick['close'],
                'volume': tick['volume']
            }
            
            return CandleEvent(
                timeframe=timeframe,
                candle=closed_candle,
                timestamp=datetime.now()
            )
    
    def get_candles(self, timeframe: str, lookback: int = 100) -> pd.DataFrame:
        """
        Get recent candles for a specific timeframe.
        
        Args:
            timeframe: '1m', '5m', '15m', '1h', or '1d'
            lookback: Number of candles to return
            
        Returns:
            DataFrame with OHLCV data
        """
        with self.lock:
            if timeframe not in self.data:
                raise ValueError(f"Invalid timeframe: {timeframe}")
            
            df = self.data[timeframe]
            return df.tail(lookback).copy()
    
    def register_callback(self, callback: Callable[[CandleEvent], None]):
        """Register a callback to be called when any candle closes."""
        self.on_candle_close_callbacks.append(callback)
    
    def _emit_event(self, event: CandleEvent):
        """Emit candle_close event to all registered callbacks."""
        for callback in self.on_candle_close_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create resampler
    resampler = CandleResampler()
    
    # Simulate loading historical data
    historical = pd.DataFrame({
        'date': pd.date_range('2024-01-01 09:15', periods=100, freq='1min'),
        'open': [100 + i * 0.1 for i in range(100)],
        'high': [101 + i * 0.1 for i in range(100)],
        'low': [99 + i * 0.1 for i in range(100)],
        'close': [100.5 + i * 0.1 for i in range(100)],
        'volume': [1000] * 100
    })
    
    resampler.preload_historical(historical)
    
    # Get 5m candles
    candles_5m = resampler.get_candles('5m')
    print(f"5m candles: {len(candles_5m)}")
    print(candles_5m.head())
