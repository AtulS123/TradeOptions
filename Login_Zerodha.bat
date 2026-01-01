@echo off
echo ==============================================
echo  ZERODHA AUTOMATED LOGIN
echo ==============================================
echo.
echo Please login to Zerodha in the browser window that opens.
echo.

python get_daily_token.py

if exist access_token.txt (
    echo.
    echo [SUCCESS] Token generated successfully!
    echo.
    timeout /t 3
) else (
    echo.
    echo [ERROR] Token generation failed.
    pause
)
