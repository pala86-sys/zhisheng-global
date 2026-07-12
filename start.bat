@echo off
cd /d "%~dp0"
echo 智勝全球 · 策略回測平台啟動中...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8765"
python -m uvicorn server:app --host 127.0.0.1 --port 8765 --reload
pause
