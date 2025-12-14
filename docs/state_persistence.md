# State Persistence

The **State Persistence Layer** ensures the bot is robust against crashes and restarts.

## Architecture

### 1. `TradeState` Logic

- **File**: `state/state_manager.py`
- **Fields Preserved**:
  - `daily_pnl`: Realized profit/loss for the day.
  - `kill_switch_active`: If the safety lock is engaged.
  - `open_positions`: Full details of active trades.

### 2. Storage Mechanism

- **JSON File**: Data is written to `trading_state.json`.
- **Atomic Writes**: Writes to a `.tmp` file first, then renames, preventing corruption during power cuts.

### 3. Rehydration Process

On startup (`main.py`):

1. **Load**: Reads the JSON file.
    - *Corruption Check*: If file is broken, starts fresh (safe mode).
    - *Date Check*: If `last_updated` was yesterday, auto-resets PnL to 0.
2. **Restore Risk**: Feeds saved PnL back into `RiskManager`.
3. **Restore Strategy**: Puts active trades back into `StrategyManager` logic.

### 4. Verification

The `verify_state.py` script (if available) can simulate crashes and date changes to prove reliability.
