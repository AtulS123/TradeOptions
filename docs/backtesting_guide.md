# Backtesting Module Guide

## Overview

The Backtesting Module allows for simulation of trading strategies against historical data. It currently supports the **VWAP Momentum Strategy** on **NIFTY 50 Futures** (simulated via synthetic volume injection if needed).

## Architecture

1. **Frontend (`Backtesting.tsx`)**:
    - Configures simulation parameters (Capital, Dates, Strategy).
    - Sends payload to `/api/backtest/run`.
    - Visualizes Equity Curve, Drawdown, and Trade Log.

2. **Backend (`server_v2.py`)**:
    - Orchestrates the `BacktestRunner`.
    - Disables the live market data loop during backtesting to prevent conflicts.

3. **Runner (`src/backtest_runner.py`)**:
    - Loads historical data (CSV).
    - **Volume Injection**: If data lacks volume (e.g., Spot data), it injects synthetic volume (5k-15k) to enable VWAP calculations.
    - **Strategy Execution**: Runs `VWAPStrategy` on each candle.
    - **Force Close**: Automatically closes all open positions at the end of the simulation to realize PnL.

4. **Analytics (`src/analytics/performance.py`)**:
    - Calculates Sharpe, Drawdown, Win Rate, etc.
    - Generates the final Trade Log.

## How to Run

1. Navigate to `http://localhost:5173/backtesting`.
2. Select **VWAP Momentum** Strategy.
3. Set **Start/End Date** and **Initial Capital**.
4. Click **Run Backtest**.

## Troubleshooting

- **0 Trades**: Ensure the strategy parameters (Target/SL) are not too tight. The engine now Force Closes positions, so you should see at least entry trades if signals are generated.
- **Missing Volume**: The runner checks for 'volume' column. If missing, it log a warning and injects synthetic data.

## Recent Updates (Jan 2026)

- Fixed "0 Trades" bug by implementing Force Close logic.
- Added Synthetic Volume for Spot Data support.
- Fixed Frontend bug where `trades` were omitted from the display.
