@echo off
chcp 65001 >nul

echo.
echo ============================================
echo   卸载开机自启动
echo ============================================
echo.

echo 正在删除任务计划...
schtasks /delete /tn "ClaudeCodeChatHistory" >nul 2>&1

if errorlevel 1 (
    echo [⚠️] 任务不存在或删除失败
) else (
    echo [✓] 任务已删除
)

echo.
echo 如果服务正在运行，请手动运行 stop_service.bat 停止
echo.
pause
