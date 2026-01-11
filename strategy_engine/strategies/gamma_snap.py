from .base import BaseStrategy
from datetime import datetime
import pandas as pd
import logging
from typing import Optional, Dict
import numpy as np

logger = logging.getLogger(__name__)

class GammaSnapStrategy(BaseStrategy):
    """
    Gamma Snap: High-Frequency Scalping Strategy.
    Combines VWAP, RSI, and Volume confirmation for rapid entries/exits.
    
    Signal Logic:
    - BUY: Close > VWAP AND RSI > 50 AND Volume > (Vol_SMA_20 * 1.2)
    - SELL: Close < VWAP AND RSI < 50 AND Volume > (Vol_SMA_20 * 1.2)
    """
    
    def __init__(self, rsi_period=14, vol_multiplier=1.2):
        self._name = "Gamma Snap"
        self.candles = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        self.current_candle = None
        self.last_candle_time = None
        
        # Parameters
        self.rsi_period = rsi_period
        self.vol_multiplier = vol_multiplier
        
        # Heartbeat tracking
        self.last_heartbeat_time = None
        
    def seed_candles(self, historical_df: pd.DataFrame):
        """
        Hydrates the strategy with historical 1-minute data.
        
        Args:
            historical_df: DF with columns ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        if historical_df.empty:
            logger.warning("Gamma Snap Seed: Empty dataframe.")
            return False

        logger.info(f"Seeding Gamma Snap with {len(historical_df)} candles...")
        
        # Ensure timestamp column
        if 'date' in historical_df.columns and 'timestamp' not in historical_df.columns:
            historical_df.rename(columns={'date': 'timestamp'}, inplace=True)

        # Ensure timestamp is datetime
        if 'timestamp' in historical_df.columns:
            historical_df['timestamp'] = pd.to_datetime(historical_df['timestamp'])
        else:
            logger.error("Gamma Snap Seed Failed: No 'timestamp' or 'date' column in data.")
            return False
        
        # Reset candles
        self.candles = historical_df.copy().sort_values('timestamp').reset_index(drop=True)
        
        # Validation: Check for volume
        vol = self.candles['volume']
        if vol.sum() == 0:
            logger.error("Gamma Snap Seed Critical: Total Volume is 0. Strategy requires volume data.")
            return False

        # Pre-calculate indicators
        self.candles = self._calculate_all_indicators(self.candles)
        
        # Check for NaN in last values
        last_row = self.candles.iloc[-1]
        if pd.isna(last_row.get('vwap')) or pd.isna(last_row.get('rsi')):
            logger.critical(f"Gamma Snap Seed Critical: Calculated indicators contain NaN.")
            return False
        
        logger.info(f"Gamma Snap Seeded. Last VWAP: {last_row['vwap']:.2f}, RSI: {last_row['rsi']:.2f}")
        return True

    @property
    def name(self) -> str:
        return self._name
        
    def _update_candle(self, tick: dict):
        """
        Aggregates ticks into 1-minute candles.
        Replicates logic from vwap.py with cumulative volume handling.
        """
        price = tick.get('last_price')
        volume = tick.get('volume', 0)
        tick_time = tick.get('timestamp', datetime.now())
        
        # Initialize first candle
        if self.current_candle is None:
            self._start_new_candle(tick_time, price, volume, tick.get('cumulative_volume', 0))
            return False

        # Check minute boundary
        current_minute = self.current_candle['timestamp'].minute
        tick_minute = tick_time.minute
        
        if tick_minute != current_minute:
            # Finalize old candle and add to dataframe
            self.candles = pd.concat([self.candles, pd.DataFrame([self.current_candle])], ignore_index=True)
            self._start_new_candle(tick_time, price, volume, tick.get('cumulative_volume', 0))
            return True  # New candle formed
            
        # Update current candle (OHLC)
        self.current_candle['high'] = max(self.current_candle['high'], price)
        self.current_candle['low'] = min(self.current_candle['low'], price)
        self.current_candle['close'] = price
        
        # Volume logic: Handle cumulative volume correctly
        curr_cum_vol = tick.get('cumulative_volume', 0)
        if curr_cum_vol > 0:
            vol_diff = curr_cum_vol - self.current_candle['start_cum_vol']
            self.current_candle['volume'] = max(0, vol_diff)
        else:
            # Fallback: sum tick volumes if cumulative not available
            self.current_candle['volume'] += volume
              
        return False
        
    def _start_new_candle(self, timestamp, price, volume, cum_vol):
        """Initialize a new candle"""
        self.current_candle = {
            'timestamp': timestamp,
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': 0,
            'start_cum_vol': cum_vol
        }

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index)
        
        Args:
            prices: Series of close prices
            period: RSI period (default 14)
            
        Returns:
            Series of RSI values
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss.replace(0, float('nan'))  # Avoid division by zero
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    def _calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate VWAP, RSI, and Volume SMA on the entire dataframe
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added indicator columns
        """
        if len(df) < self.rsi_period:
            return df
            
        # VWAP Calculation (Intraday cumulative)
        price = df['close']
        vol = df['volume']
        
        df['cum_pairs'] = (price * vol).cumsum()
        df['cum_vol'] = vol.cumsum()
        df['vwap'] = df['cum_pairs'] / df['cum_vol'].replace(0, float('nan'))
        
        # RSI Calculation
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        
        # Volume SMA (20-period)
        df['vol_sma_20'] = df['volume'].rolling(window=20).mean()
        
        return df

    def _calculate_indicators(self):
        """
        Updates indicators on the candles dataframe and returns latest values
        """
        if len(self.candles) < max(20, self.rsi_period):
            return None

        self.candles = self._calculate_all_indicators(self.candles)
        return self.candles.iloc[-1]

    def _log_heartbeat(self, latest_data):
        """
        Logs heartbeat every minute showing current state
        
        Args:
            latest_data: Latest candle with indicators
        """
        now = datetime.now()
        
        # Only log once per minute
        if self.last_heartbeat_time and (now - self.last_heartbeat_time).total_seconds() < 60:
            return
            
        self.last_heartbeat_time = now
        
        price = latest_data['close']
        vwap = latest_data['vwap']
        rsi = latest_data['rsi']
        vol = latest_data['volume']
        avg_vol = latest_data['vol_sma_20']
        
        vol_ratio = vol / avg_vol if avg_vol > 0 else 0
        
        logger.info(
            f"GAMMA SNAP HEARTBEAT: "
            f"Price={price:.2f} | "
            f"VWAP={vwap:.2f} | "
            f"RSI={rsi:.2f} | "
            f"VolRatio={vol_ratio:.2f}x"
        )

    def process_tick(self, tick_data: dict) -> Optional[dict]:
        """
        Main strategy logic - processes each tick and generates signals.
        
        Signal Generation:
        - BUY: Close > VWAP AND RSI > 50 AND Volume > (Vol_SMA_20 * vol_multiplier)
        - SELL: Close < VWAP AND RSI < 50 AND Volume > (Vol_SMA_20 * vol_multiplier)
        
        Args:
            tick_data: Dictionary containing tick information
            
        Returns:
            Signal dictionary or None
        """
        # Check for zero volume warning
        volume = tick_data.get('volume', 0)
        if volume == 0 and tick_data.get('cumulative_volume', 0) == 0:
            logger.warning("Gamma Snap: Received tick with zero volume. Strategy requires volume data.")
        
        # Update candle aggregation
        new_candle_formed = self._update_candle(tick_data)
        
        if not new_candle_formed:
            return None
            
        # Only run logic on candle close
        if len(self.candles) < max(20, self.rsi_period):
            logger.debug(f"Gamma Snap: Waiting for more data. Current candles: {len(self.candles)}")
            return None
            
        latest = self._calculate_indicators()
        
        if latest is None:
            return None
        
        # Log heartbeat
        self._log_heartbeat(latest)
        
        # Extract values
        price = latest['close']
        vwap = latest['vwap']
        rsi = latest['rsi']
        vol = latest['volume']
        avg_vol = latest['vol_sma_20']
        
        # Skip if indicators are NaN
        if pd.isna(vwap) or pd.isna(rsi) or pd.isna(avg_vol):
            logger.warning("Gamma Snap: Indicators contain NaN, skipping signal generation")
            return None
        
        # Calculate volume threshold
        vol_threshold = avg_vol * self.vol_multiplier
        
        # Signal generation logic
        action = None
        
        # BUY Signal
        if price > vwap and rsi > 50 and vol > vol_threshold:
            action = "BUY"
            logger.info(
                f"GAMMA SNAP BUY SIGNAL: "
                f"Price={price:.2f} > VWAP={vwap:.2f}, "
                f"RSI={rsi:.2f} > 50, "
                f"Vol={vol:.0f} > {vol_threshold:.0f}"
            )
            
        # SELL Signal
        elif price < vwap and rsi < 50 and vol > vol_threshold:
            action = "SELL"
            logger.info(
                f"GAMMA SNAP SELL SIGNAL: "
                f"Price={price:.2f} < VWAP={vwap:.2f}, "
                f"RSI={rsi:.2f} < 50, "
                f"Vol={vol:.0f} > {vol_threshold:.0f}"
            )
        
        if action:
            return {
                "action": action,
                "token": tick_data.get('instrument_token'),
                "tag": "GAMMA_SNAP",
                "price": price,
                "vwap": vwap,
                "rsi": rsi
            }
            
        return None
