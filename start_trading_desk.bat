@echo off
echo ==============================================
echo Starting Automated Alpha Trading Desk...
echo ==============================================

:: Get the directory of this script
set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash if present (though %~dp0 has one)
:: Build full path to frontend
set "FRONTEND_DIR=%SCRIPT_DIR%01 Figma"

echo [1/3] Starting Backend API Server...
:: Using pushd to ensure we are in the script directory
pushd "%SCRIPT_DIR%"
start "AlgoBackend" cmd /k "python server_v2.py"
popd

echo [2/3] Starting Frontend Dashboard...
:: Explicitly changing directory inside the new window command
echo Target Frontend Dir: "%FRONTEND_DIR%"
start "AlgoFrontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm install && npm run dev"

echo [3/3] Waiting for services to boot (10 seconds)...
timeout /t 10 /nobreak >nul

echo Launching Default Browser...
start http://localhost:5173

echo ==============================================
echo  TRADING DESK LAUNCHED!
echo ==============================================
