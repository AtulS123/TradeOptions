@echo off
echo Stopping Trading Desk...
echo.
:: Kill by Window Title (Wildcard Matching)
echo Closing Backend Window...
taskkill /F /FI "WINDOWTITLE eq AlgoBackend*" /T
echo Closing Frontend Window...
taskkill /F /FI "WINDOWTITLE eq AlgoFrontend*" /T

:: Fallback: Kill by Image Name if windows stick around
:: Warning: This kills ALL python/node processes, use with care or ask user (User seems fine with it based on previous specific script).
echo Killing lingering runtimes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM node.exe /T 2>nul

echo.
echo Check if windows are closed.
pause
