"""
Telescope Package - Multi-Timeframe Pattern Detection Engine

Contains:
- historical_loader: Loads and caches NIFTY historical data
- resampler: Aggregates 1m → 5m, 15m, 1h, 1d candles
- pattern_scanner: Detects candlestick, geometric, and indicator patterns
- signal_tracker: Manages signal lifecycle (entry → SL/Target → exit)
"""

__version__ = "0.1.0"
