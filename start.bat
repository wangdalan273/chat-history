@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================
echo   Claude Code Chat History v2.0
echo ============================================
echo.

echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo.
    echo Please install Python 3.7+
    echo 1. Visit https://www.python.org/downloads/
    echo 2. Download and install Python
    echo 3. Check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
python --version
echo [OK] Python is installed
echo.

echo [2/5] Checking Flask...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Installing Flask...
    pip install flask
    if errorlevel 1 (
        echo [ERROR] Flask install failed
        echo.
        echo Please run: pip install flask
        pause
        exit /b 1
    )
) else (
    echo [OK] Flask is installed
)
echo.

echo [3/5] Checking port 13001...
netstat -ano | findstr ":13001" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] Port 13001 is in use
    echo.
    netstat -ano | findstr ":13001"
    echo.
    echo Run stop_service.bat to free the port
    pause
    exit /b 1
)
echo [OK] Port 13001 is available
echo.

echo [4/5] Checking project files...
set "PROJECT_DIR=%~dp0"
if not exist "%PROJECT_DIR%scripts\web_server.py" (
    echo [ERROR] web_server.py not found
    echo.
    echo Please run from project root directory
    pause
    exit /b 1
)
echo [OK] Project files ready
echo.

echo [5/5] Starting server...
echo.
echo ============================================
echo   Server is starting...
echo ============================================
echo.
echo URL: http://localhost:13001
echo.
echo Press Ctrl+C to stop the server
echo.

set /p autostart=Enable auto-start on boot? (Y/N):
if /i "%autostart%"=="Y" (
    echo.
    echo Setting up auto-start...
    set "TASK_NAME=ClaudeCodeChatHistory"
    schtasks /delete /tn "%TASK_NAME%" >nul 2>&1
    schtasks /create /tn "%TASK_NAME%" /tr "pythonw \"\"%PROJECT_DIR%scripts\web_server.py\"\"" /sc onlogon /rl highest /f >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Failed - need admin rights
    ) else (
        echo [OK] Auto-start enabled
        echo Run uninstall_service.bat to disable
    )
    echo.
)

set /p choice=Open browser now? (Y/N):
if /i "%choice%"=="Y" (
    timeout /t 2 >nul
    start http://localhost:13001
    echo.
    echo [OK] Browser opened
    echo.
)

echo Starting server in background...
start /B pythonw "%PROJECT_DIR%scripts\web_server.py"

timeout /t 3 >nul

echo.
echo [OK] Server is running in background
echo.
echo URL: http://localhost:13001
echo.
echo You can close this window now
echo To stop: Run stop_service.bat
echo.
pause
