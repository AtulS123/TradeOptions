# Risk Management Architecture

The **Risk Management** layer acts as a strict **Gatekeeper**, protecting the account from ruin and poor-quality trades. It is designed to be modular and mathematically rigorous.

## Core Components

### 1. Risk Manager (`risk/risk_manager.py`)

- **Role**: The Gatekeeper (Orchestrator).
- **Responsibilities**:
  - **Kill Switch**: Automatically halts trading if Daily PnL drops below a limit (default 5%).
  - **R:R Validation**: Rejects any trade setup with a Risk:Reward ratio < 2.0.
  - **Delegation**: Asks the active Strategy Plugin for the position size.

### 2. Risk Strategy Plugin (`risk/strategies/kelly.py`)

- **Role**: The Sizing Engine.
- **Algorithm**: **Quarter-Kelly Criterion**.
- **Formula**:
  - $f^* = (p(b+1) - 1) / b$
  - $Size = (f^* / 4) * Capital$
- **Safety**:
  - **Max Risk Cap**: Hard limit of 5% capital per trade.
  - **Rounding**: Rounds down to the nearest valid lot size (25).

### 3. Base Interface (`risk/strategies/base.py`)

- **Role**: The Contract.
- **Goal**: Allows swapping "Kelly" for "FixedFractional" or other models easily.

## Usage

### Validation Endpoint

The system exposes an API for checking trades manually or via UI:
`GET /validate-trade?entry=100&sl=90&target=120`

**Response:**

```json
{
    "approved": true,
    "reason": "Approved",
    "suggested_qty": 425
}
```

## Configuration

Initialized in `main.py`:

```python
risk_manager = RiskManager(
    total_capital=100000.0,
    max_daily_loss_pct=0.05,  # 5% Max Daily Loss
    min_risk_reward_ratio=2.0 # 1:2 R:R Minimum
)
```
