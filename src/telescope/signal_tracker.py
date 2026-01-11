"""
Signal Tracker for Project Telescope

Manages the complete lifecycle of trading signals:
- ACTIVE: Signal is valid, tracking for SL/Target
- HIT_TARGET: Reached 1:2 R/R, moved to history
- HIT_SL: Stop loss triggered, moved to history
- EXPIRED: Time-based expiry (optional)

Tracks signals across all 5 timeframes simultaneously.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class Signal:
    """Trading signal with full lifecycle data."""
    id: str
    pattern_name: str
    timeframe: str
    timestamp: datetime
    signal_type: str  # "CE" (bullish) or "PE" (bearish)
    entry_price: float
    stop_loss: float
    target: float
    candle_index: int
    confidence: float
    atr: float
    metadata: Dict = field(default_factory=dict)
    
    # Lifecycle fields
    status: str = "ACTIVE"  # ACTIVE, HIT_TARGET, HIT_SL, EXPIRED
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    bars_held: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime to ISO string
        if self.timestamp:
            data['timestamp'] = self.timestamp.isoformat()
        if self.exit_time:
            data['exit_time'] = self.exit_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Signal':
        """Create Signal from dictionary."""
        # Convert ISO strings back to datetime
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'exit_time' in data and isinstance(data['exit_time'], str):
            data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        return cls(**data)


class SignalTracker:
    """
    Manages signal lifecycle across all timeframes.
    
    Features:
    - Track active signals
    - Check invalidation (SL/Target hits)
    - Calculate running P&L
    - Store history
    - Persist to disk
    """
    
    def __init__(self, persist_path: str = "data/telescope_signals.json"):
        self.active_signals: Dict[str, Signal] = {}  # signal_id -> Signal
        self.historical_signals: List[Signal] = []
        self.persist_path = Path(persist_path)
        
        # Load persisted signals
        self._load()
        
        logger.info(f"SignalTracker initialized: {len(self.active_signals)} active, {len(self.historical_signals)} historical")
    
    def add_signal(self, signal: Signal) -> str:
        """
        Add a new signal to tracking.
        
        Args:
            signal: Signal object from pattern detection
            
        Returns:
            signal_id: Unique identifier
        """
        # Generate unique ID
        signal.id = f"{signal.timeframe}_{signal.pattern_name}_{int(signal.timestamp.timestamp())}"
        
        # Add to active tracking
        self.active_signals[signal.id] = signal
        
        logger.info(f"New signal: {signal.pattern_name} ({signal.signal_type}) on {signal.timeframe} @ {signal.entry_price}")
        
        # Persist
        self._save()
        
        return signal.id
    
    def update_price(self, timeframe: str, current_price: float, timestamp: datetime):
        """
        Update all signals for a timeframe with current price.
        Checks for SL/Target hits and updates P&L.
        
        Args:
            timeframe: '1m', '5m', etc.
            current_price: Current market price
            timestamp: Current time
        """
        invalidated = []
        
        for signal_id, signal in list(self.active_signals.items()):
            if signal.timeframe != timeframe:
                continue
            
            # Update bars held
            signal.bars_held += 1
            
            # Check for invalidation
            should_close, reason = self._check_invalidation(signal, current_price)
            
            if should_close:
                # Close the signal
                signal.status = reason
                signal.exit_price = current_price
                signal.exit_time = timestamp
                
                # Calculate P&L
                signal.pnl, signal.pnl_percent = self._calculate_pnl(signal)
                
                # Move to history
                self.historical_signals.append(signal)
                invalidated.append(signal_id)
                
                logger.info(f"Signal closed: {signal.pattern_name} ({signal.status}) PnL: {signal.pnl:.2f} ({signal.pnl_percent:.2f}%)")
            else:
                # Update running P&L
                signal.pnl, signal.pnl_percent = self._calculate_pnl(signal, current_price)
        
        # Remove invalidated signals from active
        for signal_id in invalidated:
            del self.active_signals[signal_id]
        
        # Persist if any changes
        if invalidated:
            self._save()
    
    def _check_invalidation(self, signal: Signal, current_price: float) -> tuple:
        """
        Check if signal should be closed.
        
        Returns:
            (should_close: bool, reason: str)
        """
        if signal.signal_type == "CE":
            # Bullish: SL below, Target above
            if current_price <= signal.stop_loss:
                return True, "HIT_SL"
            elif current_price >= signal.target:
                return True, "HIT_TARGET"
        else:
            # Bearish: SL above, Target below
            if current_price >= signal.stop_loss:
                return True, "HIT_SL"
            elif current_price <= signal.target:
                return True, "HIT_TARGET"
        
        return False, ""
    
    def _calculate_pnl(self, signal: Signal, current_price: Optional[float] = None) -> tuple:
        """
        Calculate P&L for a signal.
        
        Args:
            signal: Signal object
            current_price: Current price (if None, uses exit_price)
            
        Returns:
            (pnl: float, pnl_percent: float)
        """
        exit_price = current_price if current_price is not None else signal.exit_price
        
        if exit_price is None:
            return 0.0, 0.0
        
        if signal.signal_type == "CE":
            # Bullish: Profit when price goes up
            pnl = exit_price - signal.entry_price
        else:
            # Bearish: Profit when price goes down
            pnl = signal.entry_price - exit_price
        
        pnl_percent = (pnl / signal.entry_price) * 100
        
        return round(pnl, 2), round(pnl_percent, 2)
    
    def get_active_signals(self, timeframe: Optional[str] = None) -> List[Signal]:
        """
        Get all active signals, optionally filtered by timeframe.
        
        Args:
            timeframe: Filter by timeframe (None = all)
            
        Returns:
            List of active signals
        """
        signals = list(self.active_signals.values())
        
        if timeframe:
            signals = [s for s in signals if s.timeframe == timeframe]
        
        # Sort by timestamp (newest first)
        signals.sort(key=lambda s: s.timestamp, reverse=True)
        
        return signals
    
    def get_historical_signals(self, limit: int = 50) -> List[Signal]:
        """
        Get recent historical signals.
        
        Args:
            limit: Maximum number to return
            
        Returns:
            List of closed signals
        """
        # Sort by exit time (newest first)
        sorted_signals = sorted(
            self.historical_signals,
            key=lambda s: s.exit_time if s.exit_time else datetime.min,
            reverse=True
        )
        
        return sorted_signals[:limit]
    
    def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Get a specific signal by ID."""
        if signal_id in self.active_signals:
            return self.active_signals[signal_id]
        
        for signal in self.historical_signals:
            if signal.id == signal_id:
                return signal
        
        return None
    
    def get_stats(self) -> Dict:
        """
        Get overall statistics.
        
        Returns:
            {
                "total_active": int,
                "total_historical": int,
                "win_rate": float,
                "avg_pnl": float,
                "by_timeframe": {...}
            }
        """
        total_active = len(self.active_signals)
        total_historical = len(self.historical_signals)
        
        # Calculate win rate
        winners = [s for s in self.historical_signals if s.status == "HIT_TARGET"]
        win_rate = (len(winners) / total_historical * 100) if total_historical > 0 else 0
        
        # Average P&L
        avg_pnl = sum(s.pnl for s in self.historical_signals) / total_historical if total_historical > 0 else 0
        
        # By timeframe
        by_timeframe = {}
        for tf in ['1m', '5m', '15m', '1h', '1d']:
            tf_signals = [s for s in self.active_signals.values() if s.timeframe == tf]
            by_timeframe[tf] = len(tf_signals)
        
        return {
            "total_active": total_active,
            "total_historical": total_historical,
            "win_rate": round(win_rate, 2),
            "avg_pnl": round(avg_pnl, 2),
            "by_timeframe": by_timeframe
        }
    
    def _save(self):
        """Persist signals to disk."""
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "active": [s.to_dict() for s in self.active_signals.values()],
                "historical": [s.to_dict() for s in self.historical_signals[-1000:]]  # Keep last 1000
            }
            
            with open(self.persist_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.debug(f"Saved {len(data['active'])} active, {len(data['historical'])} historical signals")
        except Exception as e:
            logger.error(f"Failed to save signals: {e}")
    
    def _load(self):
        """Load persisted signals."""
        if not self.persist_path.exists():
            return
        
        try:
            with open(self.persist_path, 'r') as f:
                data = json.load(f)
            
            # Load active signals
            for sig_data in data.get('active', []):
                signal = Signal.from_dict(sig_data)
                self.active_signals[signal.id] = signal
            
            # Load historical signals
            for sig_data in data.get('historical', []):
                signal = Signal.from_dict(sig_data)
                self.historical_signals.append(signal)
            
            logger.info(f"Loaded {len(self.active_signals)} active, {len(self.historical_signals)} historical signals")
        except Exception as e:
            logger.error(f"Failed to load signals: {e}")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create tracker
    tracker = SignalTracker(persist_path="test_signals.json")
    
    # Create test signal
    from src.telescope.pattern_scanner import Signal as ScannerSignal
    
    test_signal = ScannerSignal(
        pattern_name="Hammer",
        timeframe="1h",
        timestamp=datetime.now(),
        signal_type="CE",
        entry_price=24500,
        stop_loss=24400,
        target=24700,
        candle_index=100,
        confidence=0.8,
        atr=50,
        metadata={}
    )
    
    # Add to tracker
    signal_id = tracker.add_signal(test_signal)
    print(f"Added signal: {signal_id}")
    
    # Simulate price updates
    tracker.update_price("1h", 24550, datetime.now())  # Profit
    tracker.update_price("1h", 24700, datetime.now())  # Hit target
    
    # Get stats
    stats = tracker.get_stats()
    print(f"Stats: {stats}")
