@echo off
chcp 65001 >nul

echo.
echo ============================================
echo   停止服务
echo ============================================
echo.

echo 正在停止 Python 进程...
taskkill /F /IM pythonw.exe 2>nul

REM 等待进程完全停止
timeout /t 2 >nul

REM 再次确认停止
taskkill /F /IM pythonw.exe 2>nul
if not errorlevel 1 (
    echo [⚠️] 服务进程仍在运行，请手动检查
)

echo.
echo [✓] 服务已停止
echo.
echo URL: http://localhost:13001
echo.
pause
