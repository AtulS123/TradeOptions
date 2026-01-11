"""
Pattern Scanner for Project Telescope

Detects technical patterns across all timeframes:
1. Candlestick Patterns (TA-Lib): Hammer, Shooting Star, Engulfing, Stars
2. Geometric Patterns (Custom): H&S, Double Top/Bottom
3. Indicator Patterns: RSI Divergence, MA Crossovers, BB Squeeze

Each pattern returns a Signal with entry, SL, target (ATR-based).
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

# Try importing TA-Lib (optional dependency)
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    logging.warning("TA-Lib not installed. Candlestick patterns will use simplified logic.")

logger = logging.getLogger(__name__)

@dataclass
class Signal:
    """Trading signal from pattern detection."""
    pattern_name: str
    timeframe: str
    timestamp: datetime
    signal_type: str  # "CE" (bullish) or "PE" (bearish)
    entry_price: float
    stop_loss: float
    target: float
    candle_index: int
    confidence: float  # 0.0 to 1.0
    atr: float
    metadata: Dict  # Pattern-specific details

class PatternScanner:
    """Detects patterns on candle close events."""
    
    def __init__(self, atr_period: int = 14, atr_multiplier: float = 1.5):
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
    
    def scan(self, df: pd.DataFrame, timeframe: str) -> List[Signal]:
        """
        Scan DataFrame for ALL patterns.
        
        Args:
            df: DataFrame with OHLCV data
            timeframe: '1m', '5m', '15m', '1h', or '1d'
            
        Returns:
            List of detected signals
        """
        signals = []
        
        if len(df) < 50:
            return signals  # Need minimum data
        
        # Calculate ATR for SL/Target
        atr = self._calculate_atr(df)
        
        # 1. Candlestick Patterns
        signals.extend(self._scan_candlestick(df, timeframe, atr))
        
        # 2. Geometric Patterns
        signals.extend(self._scan_geometric(df, timeframe, atr))
        
        # 3. Indicator Patterns
        signals.extend(self._scan_indicators(df, timeframe, atr))
        
        return signals
    
    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """Calculate Average True Range."""
        df = df.copy()
        df['prev_close'] = df['close'].shift(1)
        
        df['tr'] = df[['high', 'low', 'prev_close']].apply(
            lambda row: max(
                row['high'] - row['low'],
                abs(row['high'] - row['prev_close']) if pd.notna(row['prev_close']) else 0,
                abs(row['low'] - row['prev_close']) if pd.notna(row['prev_close']) else 0
            ),
            axis=1
        )
        
        atr = df['tr'].rolling(window=self.atr_period).mean().iloc[-1]
        return atr if pd.notna(atr) else df['close'].iloc[-1] * 0.01  # 1% fallback
    
    def _create_signal(self, pattern_name: str, signal_type: str, df: pd.DataFrame, 
                       timeframe: str, atr: float, confidence: float = 0.7, metadata: Dict = None) -> Signal:
        """Create a standardized signal with ATR-based SL/Target."""
        latest = df.iloc[-1]
        entry_price = latest['close']
        
        # ATR-based risk/reward
        risk = atr * self.atr_multiplier
        reward = risk * 2  # 1:2 ratio
        
        if signal_type == "CE":
            stop_loss = entry_price - risk
            target = entry_price + reward
        else:
            stop_loss = entry_price + risk
            target = entry_price - reward
        
        return Signal(
            pattern_name=pattern_name,
            timeframe=timeframe,
            timestamp=latest['date'] if 'date' in df.columns else datetime.now(),
            signal_type=signal_type,
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            target=round(target, 2),
            candle_index=len(df) - 1,
            confidence=confidence,
            atr=round(atr, 2),
            metadata=metadata or {}
        )
    
    # ============================================
    # 1. CANDLESTICK PATTERNS (TA-Lib)
    # ============================================
    
    def _scan_candlestick(self, df: pd.DataFrame, timeframe: str, atr: float) -> List[Signal]:
        """Detect candlestick patterns using TA-Lib."""
        signals = []
        
        if not HAS_TALIB:
            return signals
        
        # Prepare data for TA-Lib
        o, h, l, c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
        
        # Bullish Patterns
        hammer = talib.CDLHAMMER(o, h, l, c)
        if hammer.iloc[-1] != 0:
            signals.append(self._create_signal("Hammer", "CE", df, timeframe, atr, 0.75))
        
        engulfing = talib.CDLENGULFING(o, h, l, c)
        if engulfing.iloc[-1] > 0:  # Bullish Engulfing
            signals.append(self._create_signal("Bullish Engulfing", "CE", df, timeframe, atr, 0.8))
        
        morning_star = talib.CDLMORNINGSTAR(o, h, l, c)
        if morning_star.iloc[-1] != 0:
            signals.append(self._create_signal("Morning Star", "CE", df, timeframe, atr, 0.85))
        
        # Bearish Patterns
        shooting_star = talib.CDLSHOOTINGSTAR(o, h, l, c)
        if shooting_star.iloc[-1] != 0:
            signals.append(self._create_signal("Shooting Star", "PE", df, timeframe, atr, 0.75))
        
        if engulfing.iloc[-1] < 0:  # Bearish Engulfing
            signals.append(self._create_signal("Bearish Engulfing", "PE", df, timeframe, atr, 0.8))
        
        evening_star = talib.CDLEVENINGSTAR(o, h, l, c)
        if evening_star.iloc[-1] != 0:
            signals.append(self._create_signal("Evening Star", "PE", df, timeframe, atr, 0.85))
        
        return signals
    
    # ============================================
    # 2. GEOMETRIC PATTERNS (Custom Logic)
    # ============================================
    
    def _scan_geometric(self, df: pd.DataFrame, timeframe: str, atr: float) -> List[Signal]:
        """Detect geometric patterns."""
        signals = []
        
        # Head & Shoulders (requires significant lookback)
        if len(df) >= 50:
            hs_signal = self._detect_head_shoulders(df, timeframe, atr)
            if hs_signal:
                signals.append(hs_signal)
        
        # Double Top/Bottom
        if len(df) >= 30:
            double_signal = self._detect_double_pattern(df, timeframe, atr)
            if double_signal:
                signals.append(double_signal)
        
        return signals
    
    def _detect_head_shoulders(self, df: pd.DataFrame, timeframe: str, atr: float) -> Optional[Signal]:
        """
        Detect Head & Shoulders pattern.
        
        Pattern: Peak1 < Peak2 (Head) > Peak3, with neckline support
        """
        # Simplified implementation - look for 3 peaks in last 50 candles
        lookback = min(50, len(df))
        recent = df.tail(lookback)
        
        # Find local peaks (highs)
        peaks = recent[recent['high'] == recent['high'].rolling(5, center=True).max()]
        
        if len(peaks) < 3:
            return None
        
        # Get last 3 peaks
        last_peaks = peaks.tail(3)
        p1, p2, p3 = last_peaks.iloc[0], last_peaks.iloc[1], last_peaks.iloc[2]
        
        # Check H&S structure: p2 (head) higher than p1 and p3 (shoulders)
        if p2['high'] > p1['high'] and p2['high'] > p3['high']:
            # Bearish H&S
            neckline = min(p1['low'], p3['low'])
            
            # Only trigger if price near/below neckline
            if df.iloc[-1]['close'] <= neckline * 1.02:
                return self._create_signal(
                    "Head & Shoulders", "PE", df, timeframe, atr, 0.9,
                    metadata={"neckline": neckline, "head": p2['high']}
                )
        
        return None
    
    def _detect_double_pattern(self, df: pd.DataFrame, timeframe: str, atr: float) -> Optional[Signal]:
        """Detect Double Top (M) or Double Bottom (W) patterns."""
        lookback = min(30, len(df))
        recent = df.tail(lookback)
        
        # Double Top: Two peaks at similar levels
        peaks = recent[recent['high'] == recent['high'].rolling(5, center=True).max()]
        
        if len(peaks) >= 2:
            last_two = peaks.tail(2)
            p1, p2 = last_two.iloc[0], last_two.iloc[1]
            
            # Check if peaks are similar (within 1%)
            if abs(p1['high'] - p2['high']) / p1['high'] < 0.01:
                support = recent.between_time('09:15', '15:30')['low'].min() if 'date' in recent.columns else recent['low'].min()
                
                # Trigger if price below midpoint
                if df.iloc[-1]['close'] < (p1['high'] + support) / 2:
                    return self._create_signal(
                        "Double Top", "PE", df, timeframe, atr, 0.85,
                        metadata={"peaks": [p1['high'], p2['high']], "support": support}
                    )
        
        # Double Bottom: Two troughs at similar levels
        troughs = recent[recent['low'] == recent['low'].rolling(5, center=True).min()]
        
        if len(troughs) >= 2:
            last_two = troughs.tail(2)
            t1, t2 = last_two.iloc[0], last_two.iloc[1]
            
            if abs(t1['low'] - t2['low']) / t1['low'] < 0.01:
                resistance = recent['high'].max()
                
                if df.iloc[-1]['close'] > (t1['low'] + resistance) / 2:
                    return self._create_signal(
                        "Double Bottom", "CE", df, timeframe, atr, 0.85,
                        metadata={"troughs": [t1['low'], t2['low']], "resistance": resistance}
                    )
        
        return None
    
    # ============================================
    # 3. INDICATOR PATTERNS
    # ============================================
    
    def _scan_indicators(self, df: pd.DataFrame, timeframe: str, atr: float) -> List[Signal]:
        """Detect indicator-based patterns."""
        signals = []
        
        # RSI Divergence
        rsi_signal = self._detect_rsi_divergence(df, timeframe, atr)
        if rsi_signal:
            signals.append(rsi_signal)
        
        # Golden Cross / Death Cross
        ma_signal = self._detect_ma_crossover(df, timeframe, atr)
        if ma_signal:
            signals.append(ma_signal)
        
        # Bollinger Squeeze
        bb_signal = self._detect_bb_squeeze(df, timeframe, atr)
        if bb_signal:
            signals.append(bb_signal)
        
        return signals
    
    def _detect_rsi_divergence(self, df: pd.DataFrame, timeframe: str, atr: float) -> Optional[Signal]:
        """Detect Regular and Hidden RSI Divergence."""
        if len(df) < 30:
            return None
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Look for divergence in last 20 candles
        recent_price = df['close'].tail(20)
        recent_rsi = rsi.tail(20)
        
        # Bullish Divergence: Price makes lower low, RSI makes higher low
        if recent_price.iloc[-1] < recent_price.iloc[-10] and recent_rsi.iloc[-1] > recent_rsi.iloc[-10]:
            return self._create_signal(
                "RSI Bullish Divergence", "CE", df, timeframe, atr, 0.8,
                metadata={"rsi": round(recent_rsi.iloc[-1], 2)}
            )
        
        # Bearish Divergence: Price makes higher high, RSI makes lower high
        if recent_price.iloc[-1] > recent_price.iloc[-10] and recent_rsi.iloc[-1] < recent_rsi.iloc[-10]:
            return self._create_signal(
                "RSI Bearish Divergence", "PE", df, timeframe, atr, 0.8,
                metadata={"rsi": round(recent_rsi.iloc[-1], 2)}
            )
        
        return None
    
    def _detect_ma_crossover(self, df: pd.DataFrame, timeframe: str, atr: float) -> Optional[Signal]:
        """Detect Golden Cross (50 EMA crosses above 200 EMA) and Death Cross."""
        if len(df) < 200:
            return None
        
        ema50 = df['close'].ewm(span=50).mean()
        ema200 = df['close'].ewm(span=200).mean()
        
        # Check for recent crossover (last 2 candles)
        prev_diff = ema50.iloc[-2] - ema200.iloc[-2]
        curr_diff = ema50.iloc[-1] - ema200.iloc[-1]
        
        # Golden Cross: 50 crosses above 200
        if prev_diff <= 0 and curr_diff > 0:
            return self._create_signal(
                "Golden Cross", "CE", df, timeframe, atr, 0.9,
                metadata={"ema50": round(ema50.iloc[-1], 2), "ema200": round(ema200.iloc[-1], 2)}
            )
        
        # Death Cross: 50 crosses below 200
        if prev_diff >= 0 and curr_diff < 0:
            return self._create_signal(
                "Death Cross", "PE", df, timeframe, atr, 0.9,
                metadata={"ema50": round(ema50.iloc[-1], 2), "ema200": round(ema200.iloc[-1], 2)}
            )
        
        return None
    
    def _detect_bb_squeeze(self, df: pd.DataFrame, timeframe: str, atr: float) -> Optional[Signal]:
        """Detect Bollinger Band Squeeze (low volatility, breakout imminent)."""
        if len(df) < 20:
            return None
        
        # Calculate Bollinger Bands
        sma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        upper = sma20 + (2 * std20)
        lower = sma20 - (2 * std20)
        bandwidth = (upper - lower) / sma20
        
        # Squeeze: Bandwidth at 6-month low
        if len(bandwidth) >= 120:
            current_bw = bandwidth.iloc[-1]
            min_bw = bandwidth.tail(120).min()
            
            if current_bw == min_bw:
                # Determine direction from recent price action
                if df['close'].iloc[-1] > sma20.iloc[-1]:
                    signal_type = "CE"
                else:
                    signal_type = "PE"
                
                return self._create_signal(
                    "Bollinger Squeeze", signal_type, df, timeframe, atr, 0.7,
                    metadata={"bandwidth": round(current_bw, 4), "sma": round(sma20.iloc[-1], 2)}
                )
        
        return None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with sample data
    test_df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=200, freq='1H'),
        'open': np.random.randn(200).cumsum() + 100,
        'high': np.random.randn(200).cumsum() + 101,
        'low': np.random.randn(200).cumsum() + 99,
        'close': np.random.randn(200).cumsum() + 100,
        'volume': np.random.randint(1000, 5000, 200)
    })
    
    scanner = PatternScanner()
    signals = scanner.scan(test_df, '1h')
    
    print(f"Detected {len(signals)} patterns:")
    for sig in signals:
        print(f"  - {sig.pattern_name} ({sig.signal_type}) @ {sig.entry_price}, SL: {sig.stop_loss}, Target: {sig.target}")
