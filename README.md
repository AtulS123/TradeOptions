# Trade Options - Automated Alpha

A modular, robust, and stateful algorithmic trading bot for NIFTY Options.

## 🚀 Key Features

### 1. Strategy Engine (`strategy_engine/`)

- **Plug-and-Play**: Strategies are independent plugins.
- **Current Strategy**: VWAP Momentum (Buys on Trend + Volume).
- [Learn More](docs/strategy_engine.md)

### 2. Risk Management (`risk/`)

- **Gatekeeper**: Enforces 1:2 Minimum Risk:Reward.
- **Position Sizing**: Quarter-Kelly Criterion with 5% Risk Cap.
- **Kill Switch**: Auto-halts if Daily Loss > 5%.
- [Learn More](docs/risk_management.md)

### 3. State Persistence (`state/`)

- **Crash Recovery**: Saves open trades and PnL to `trading_state.json`.
- **Auto-Restoration**: Resumes exactly where you left off on restart.
- **Daily Reset**: Automatically resets metrics at midnight.
- [Learn More](docs/state_persistence.md)

### 4. Real-Time Dashboard (`01 Figma/`)

- **Live Monitoring**: Tracks active paper trades in real-time.
- **PnL Tracking**: Updates profit/loss every second.
- **Manual Control**: "Close Position" button for manual intervention.
- [Learn More](docs/frontend_guide.md)

## 🛠️ Setup & Running

1. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   npm install  # In '01 Figma/' folder
   ```

2. **Start Backend**:

   ```bash
   uvicorn main:app --reload
   ```

3. **Start Frontend**:

   ```bash
   cd "01 Figma"
   npm run dev
   ```

4. **Access**:
   - Dashboard: <http://localhost:3000>
   - API Docs: <http://localhost:8000/docs>
