# Backtest Engine

The Backtest Engine is a core component of the Trade Options platform, allowing users to validate trading strategies against historical data before deployment.

## Architecture

The engine is designed to be lightweight and fast, running entirely in-memory for the duration of the simulation.

### Core Components

1. **BacktestBroker (`src/broker/backtest_broker.py`)**
    - Implements the `IVirtualBroker` interface.
    - Simulates instantaneous order fills at the requested price.
    - Maintains an in-memory ledger of trades and active positions.
    - Does **not** persist state to disk, ensuring simulations don't corrupt live trading state.

2. **BacktestRunner (`src/backtest_runner.py`)**
    - Orchestrates the simulation loop.
    - Loads historical data (currently purely synthetic options data).
    - Iterates through the data minute-by-minute.
    - Feeds "ticks" to the strategy instance.
    - Executes strategy signals via the `BacktestBroker`.
    - Tracks account equity and calculates performance metrics (Win Rate, Net Profit, etc.).

3. **API Layer (`POST /api/backtest/run`)**
    - Exposes the engine to the frontend.
    - Accepts parameters: `strategy`, `start_date`, `end_date`, `capital`.
    - Returns the Equity Curve (time-series) and Summary Metrics.

## Running a Backtest

### Via UI

1. Navigate to the "Backtesting" tab in the Dashboard.
2. Click **"Run Backtest (Real)"**.
3. The chart will update with the performance of the VWAP Momentum strategy over the sample period (Jan 2015).

### Via Python Script

A verification script is available in the root directory:

```bash
python verify_backtest.py
```

## Data Source

Currently, the engine uses `data/backtest/synthetic_options.csv`.
- **Note**: This synthetic data lacks Volume information.
- **Workaround**: The `BacktestRunner` mocks volume (flat 10,000 per tick) to ensure volume-based strategies (like VWAP) function mechanically, though the signals may not be historically accurate until real volume data is ingested.

## Future Improvements

- [ ] Ingest real historical data (with Volume/OI).
- [ ] Support Multi-Leg strategies in Backtest Broker.
- [ ] Add Slippage and Transaction Cost modeling to the Backtest Broker.
