"""
Historical Data Loader for Project Telescope

Loads NIFTY 1-minute historical data from CSV, converts to Parquet,
and provides API for querying date ranges.

Answers to user questions:
1. Historical Data Source: Loads from existing nifty_spot_1min.csv (2015-2024, 975k candles)
2. For newer data: Can fetch from Kite API (last 60 days) or yfinance
3. Storage: Converts CSV → Parquet for 10x faster loading
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class HistoricalDataLoader:
    """Manages historical 1-minute NIFTY data for pattern scanning."""
    
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        self.csv_path = self.base_path / "historical" / "nifty_spot_1min.csv"
        self.parquet_path = self.base_path / "nifty_1m.parquet"
        self._cache: Optional[pd.DataFrame] = None
        
    def load(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Load historical data with smart caching.
        
        Priority:
        1. In-memory cache (if available)
        2. Parquet file (fastest)
        3. CSV file (convert to Parquet for next time)
        
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        if self._cache is not None and not force_reload:
            logger.info(f"Using in-memory cache ({len(self._cache)} candles)")
            return self._cache
        
        # Try loading from Parquet
        if self.parquet_path.exists() and not force_reload:
            logger.info(f"Loading from Parquet: {self.parquet_path}")
            df = pd.read_parquet(self.parquet_path)
            self._cache = df
            logger.info(f"Loaded {len(df)} candles from {df.iloc[0]['date']} to {df.iloc[-1]['date']}")
            return df
        
        # Load from CSV and convert
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Historical data not found: {self.csv_path}")
        
        logger.info(f"Loading from CSV: {self.csv_path}")
        df = pd.read_csv(self.csv_path)
        
        # Standardize columns
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        # Ensure required columns
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                if col == 'volume':
                    df['volume'] = 0  # CSV might not have volume
                else:
                    raise ValueError(f"Missing required column: {col}")
        
        df = df[required_cols]
        
        # Save as Parquet for faster loading next time
        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.parquet_path, index=False)
        logger.info(f"Saved to Parquet: {self.parquet_path}")
        
        self._cache = df
        logger.info(f"Loaded {len(df)} candles from {df.iloc[0]['date']} to {df.iloc[-1]['date']}")
        return df
    
    def get_range(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get candles within a specific date range."""
        df = self.load()
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        return df[mask].copy()
    
    def get_latest(self, lookback_days: int = 365) -> pd.DataFrame:
        """Get most recent N days of data."""
        df = self.load()
        if len(df) == 0:
            return df
        
        end_date = df['date'].max()
        start_date = end_date - timedelta(days=lookback_days)
        
        return self.get_range(start_date, end_date)
    
    def get_data_range(self) -> tuple:
        """Get the date range available in the dataset."""
        df = self.load()
        if len(df) == 0:
            return None, None, 0
        
        return df['date'].min(), df['date'].max(), len(df)
