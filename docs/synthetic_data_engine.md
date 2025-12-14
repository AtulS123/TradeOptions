# Synthetic Data Engine

## Overview

The Synthetic Data Engine generates theoretical option prices for historical Nifty Index data. This serves as the foundation for the Backtest Broker, allowing us to simulate trading over long historical periods without relying on expensive or unavailable tick-level option history.

## Generation Logic (`src/data/generate_synthetic_feed.py`)

### 1. Data Ingestion

- **Inputs**:
  - `data/historical/nifty_spot_1min.csv`: Minute-level Spot prices.
  - `data/historical/india_vix_1min.csv`: Minute-level Volatility Index.
- **Process**: Data is inner-joined on the minute timestamp to ensure complete alignment.

### 2. Core Calculations

- **ATM Strike**: Calculated dynamically for each minute as `Round(Nifty_Spot / 50) * 50`.
- **DTE (Days to Expiry)**:
  - Calculates the "Next Thursday" for every timestamp.
  - Assumes expiry at **15:30** on that Thursday.
  - Handles market holidays or expiration roll-overs simplified by ensuring DTE is strictly positive (shifts to next week if current time > 15:30 Thursday).
- **Volatility ($\sigma$)**: Derived from India VIX as `VIX / 100`.
- **Risk-Free Rate ($r$)**: Hardcoded to **7%** (0.07).

### 3. Pricing Model

We use a **Vectorized Black-Scholes-Merton** model:

- **Inputs**: $S$ (Spot), $K$ (ATM Strike), $T$ (DTE in Years), $r$ (0.07), $\sigma$ (VIX/100).
- **Outputs**: Theoretical Call and Put premiums.

### 4. Skew Calibration

- **Base Theory**: Black-Scholes assumes log-normal distribution and constant volatility across strikes, often underpricing OTM/ATM options in high-demand markets.
- **Calibration**: Based on live market verification (Phase 3.1), we observed a **~6% premium** in market prices over theoretical BS prices for ATM options.
- **Adjustment**: A multiplier of **1.06** is applied to all theoretical prices.

## Output Data

- **File**: `data/backtest/synthetic_options.csv`
- **Format**:
  - `datetime`: Timestamp (Index)
  - `nifty_close`: Underlying Spot Price
  - `vix_close`: Volatility Index
  - `atm_strike`: The theoretical ATM strike used
  - `dte_days`: Exact fractional days to expiry
  - `call_price`: Calibrated Call Premium
  - `put_price`: Calibrated Put Premium

## Usage

This file is ingested by the `BacktestBroker` to simulate order filling. Since it contains theoretical "mid" prices, the broker simulation should apply appropriate slippage/spread logic on top of these values.
