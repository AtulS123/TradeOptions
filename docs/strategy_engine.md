# Strategy Engine Architecture

The **Strategy Engine** is designed to be a "Plug-and-Play" system, allowing developers to add new trading logic without modifying the core system integration.

## Core Components

### 1. Strategy Interface (`strategies/base.py`)

- **Role**: The Contract.
- **Goal**: Ensures all strategies expose the same methods.
- **Key Method**: `process_tick(self, tick_data: dict) -> Optional[dict]`.

### 2. Strategy Manager (`strategy_manager.py`)

- **Role**: The Orchestrator.
- **Goal**: Routes market data ticks to all registered strategies.
- **Functionality**:
  - `register_strategy(strategy)`: Adds a new strategy to the loop.
  - `on_tick(tick)`: Iterates through strategies and collects signals.

### 3. Strategy Plugins (`strategies/vwap.py`, etc.)

- **Role**: The Logic.
- **Goal**: Encapsulate specific trading rules.
- **Current Plugins**:
  - **VWAP Momentum**: Buys when Price > VWAP > EMA and Volume spikes.

## Integration

The system is integrated into `main.py`:

```python
# Initialization
strategy_manager = StrategyManager()
vwap_strategy = VWAPStrategy()
strategy_manager.register_strategy(vwap_strategy)

# Runtime
async def market_data_loop():
    # ...
    signals = strategy_manager.on_tick(nifty_tick)
```

## Adding a New Strategy

1. Create `strategies/super_trend.py`.
2. Inherit from `BaseStrategy`.
3. Implement `process_tick`.
4. Register it in `main.py`.
