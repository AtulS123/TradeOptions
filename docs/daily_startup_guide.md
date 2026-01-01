# Daily Trading Desk Routine

This guide outlines the steps to initialize, run, and shutdown the Automated Alpha Trading Desk each day.

## Prerequisites

- Ensure you have an active internet connection.
- Ensure your Kite Connect API credentials are valid.

---

## 1. Morning Login (One-time per day)

Use `Login_Zerodha.bat` to generate a fresh access token for the day.

**Steps:**

1. Double-click **`Login_Zerodha.bat`**.
2. A browser window or command prompt instruction will appear asking you to login to Zerodha.
3. Complete the login process in the automated browser/window.
4. Once successful, the script will verify that `access_token.txt` has been created/updated.
5. The window will confirm `[SUCCESS] Token generated successfully!`.

> **Note:** This token is valid for the entire trading day (until roughly 7:30 AM the next day). You do not need to repeat this step unless the application reports an "Invalid Token" error.

---

## 2. Start the Trading Desk

Use `start_trading_desk.bat` to launch the full system (Backend + Frontend).

**Steps:**

1. Double-click **`start_trading_desk.bat`**.
2. This will open two command windows:
   - **AlgoBackend**: Runs the Python API server.
   - **AlgoFrontend**: Runs the React dashboard.
3. After a few seconds, your default web browser will automatically open to `http://localhost:5173`.

**Verification:**

- **Status Badge:** Look for the "Connected" badge on the top right of the dashboard.
- **Data:** Ensure NIFTY Spot Price and Option Chain data are populating.

---

## 3. During the Day

- Monitor the dashboard at `http://localhost:5173`.
- **Manual Trades:** You can execute manual trades using the "Manual Execution" panel.
- **Auto-Trading:** Strategies will trigger automatically if configured.
- **Logs:** Check the `AlgoBackend` window for real-time logs and signals.

---

## 4. End of Day / Stopping

Use `Stop_Trading_Desk.bat` to cleanly shut down all services.

**Steps:**

1. Double-click **`Stop_Trading_Desk.bat`**.
2. This will force-close the Backend (`python.exe`) and Frontend (`node.exe`) processes associated with the desk.

> **Warning:** This script terminates *all* Python and Node processes started by the desk. Ensure you don't have other critical Python scripts running in the background found by the task killer.

---

## Troubleshooting

### "Token Invalid" or "Disconnected"

- If the dashboard says "Disconnected" or logs show 403 errors:
  1. Close everything using `Stop_Trading_Desk.bat`.
  2. Re-run `Login_Zerodha.bat`.
  3. Start `start_trading_desk.bat` again.

### "Backend Unreachable"

- Check the **AlgoBackend** command window for error messages.
- Common issues:
  - Port 8001 is execution blocked (restart computer or kill python tasks).
  - Config errors in `.env`.
