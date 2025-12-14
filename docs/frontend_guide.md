# Frontend Dashboard Guide

The dashboard is built with **Next.js** and **Tailwind CSS** (via the `01 Figma` project).

## Integration Architecture

### Polling Mechanism

- **File**: `PaperTrades.tsx`
- **Frequency**: Every 1000ms (1 second).
- **Endpoint**: `GET http://localhost:8000/paper-trades`

### Live Data ("Ghost Position" Fix)

The Backend actively subscribes to the market data for *all* open positions, not just the ATM ones. This ensures that even if a trade moves deep ITM/OTM, you still see its live PnL.

### Features

1. **Active Simulations**:
    - Shows all open paper trades.
    - Color-coded PnL (Green/Red).
    - Real-time updates.

2. **Manual Control**:
    - **Close Button**: Sends `DELETE /trade/{token}` request.
    - **Backend Action**: The backend calculates the *final* PnL using the live price at that exact second, updates the Risk Manager, and then deletes the position.

3. **Offline State**:
    - If the backend goes down, the UI shows a "Reconnecting..." badge but preserves the last known data to avoid flickering.
