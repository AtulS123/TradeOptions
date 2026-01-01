# Technical Capability Report: Paper Trading Mode

## Executive Summary

The system is currently hard-wired for **Paper Trading Mode** at the application level. It successfully consumes live market data from Zerodha but executes all trades virtually using a `PaperBroker` class. State is persisted locally to ensure resilience against restarts.

---

## 1. Mode Switching

**Current Status:** [Hardcoded]

- There is **no dynamic toggle** (e.g., `LIVE_TRADING=True/False` flag) in the configuration files (`.env` or `config.py`) that switches the execution engine between Live and Paper.
- `server_v2.py` explicitly initializes `PaperBroker`:

  ```python
  # server_v2.py Line 51
  paper_broker = PaperBroker(state_manager, slippage_pct=0.0005)
  ```

- To switch to Live trading, code changes would be required to instantiate a real `ZerodhaBroker` instead.

## 2. Order Execution Mocking

**Current Status:** [Implemented - High Fidelity]

- **Class:** `src.broker.paper_broker.PaperBroker`
- **Simulation Logic:**
  - **Interceptor:** Intercepts `BUY`/`SELL` signals.
  - **Slippage:** Applies a configurable slippage model (default 0.05% of LTP) to simulate realistic fill prices.
    - Buy Price = MRP * (1 + slippage)
    - Sell Price = MRP * (1 - slippage)
  - **Transaction Costs:** Uses a `CostModel` (brokerage + STT + taxes) to calculate net P&L, ensuring the paper results are net of potential real-world fees.
  - **Latency:** Zero artificial latency simulated; execution is instantaneous upon function call.

## 3. Portfolio Tracking

**Current Status:** [Implemented - Stateful]

- **State Management:** Uses `state.state_manager.StateManager` backed by a JSON file (`trading_state.json`).
- **Metrics Tracked:**
  - `daily_pnl`: Aggregated Realized P&L for the day.
  - `open_positions`: Detailed map of active virtual positions (Symbol, Qty, Entry Price, Stops).
- **Reset Logic:** Automatically resets `daily_pnl` and `open_positions` if the system detects the date has changed since the last update.
- **Limits:** `PaperBroker.get_limits()` currently returns a hardcoded mock cash balance of `100,000.0`. `RiskManager` (initialized in `server_v2.py`) manages a separate virtual capital pool (`total_capital=200000.0`).

## 4. Data Dependency

**Current Status:** [Live Data Driven]

- **Source:** The paper trading engine is **fully dependent on Live Data** from Zerodha Kite Connect.
- **Workflow:**
  1. `market_data_loop` in `server_v2.py` polls `kite.quote()` for NIFTY 50 and Option Chain data.
  2. Live `last_price` is passed to the Strategy Engine.
  3. Signals generated are passed to `PaperBroker`.
  4. `PaperBroker` uses the *current active market price* (not historical) to simulate the execution.
- **Requirement:** A valid API Key and fresh Access Token are required even for Paper Trading to fetch the underlying market ticks.

---

## Gap Analysis & Recommendations

| Feature | Status | Recommendation |
| :--- | :--- | :--- |
| **Live/Paper Toggle** | 🔴 Missing | Implement a `TRADING_MODE` env var to dynamically inject the correct Broker instance. |
| **Capital Sync** | 🟡 Partial | specific `PaperBroker` limits (100k) do not match `RiskManager` config (200k). Centralize capital config. |
| **Order Latency** | ⚪ Missing | Consider adding `asyncio.sleep()` in `PaperBroker` to simulate network latency for high-frequency strategies. |
