# Frontend Dashboard Guide

The dashboard is built with **Next.js** and **Tailwind CSS** (via the `01 Figma` project).

## Integration Architecture

### Polling Mechanism

- **File**: `PaperTrades.tsx`
- **Frequency**: Every 1000ms (1 second).
- **Endpoint**: `GET http://localhost:8001/paper-trades`

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

3. **Manual Position Taker**:
    - **Trigger**: Click any Green/Red LTP in the Option Chain.
    - **Modal**: Opens an "Order Entry" modal auto-populated with the Strike/Type.
    - **Execution**: Supports MARKET and LIMIT orders via `/api/place-order`.
    - **Validation**: Checks for Margin Shortfall before allowing execution.

4. **Order History**:
    - **Orders Tab**: Displays a log of all attempted orders (Accepted, Rejected, or Executed).
    - **Persistence**: "REJECTED" orders (e.g. Market Closed) are saved for audit trails.

5. **Offline State**:
    - If the backend goes down, the UI shows a "Reconnecting..." badge but preserves the last known data to avoid flickering.
