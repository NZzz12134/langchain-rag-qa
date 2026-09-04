@echo off
title RAG QA System Launcher
echo ============================================
echo   RAG Knowledge Base QA System - DEV MODE
echo   Requires: MySQL 8.0 + Memurai (Redis) running
echo ============================================
echo.

rem check if already running
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [!] Backend already running on port 8000. Run stop_dev.bat first.
    pause
    exit /b
)

echo [1/3] Starting backend API on port 8000 ...
start "RAG-Backend" /d "%~dp0backend" cmd /k "title RAG-Backend && set PYTHONIOENCODING=utf-8 && .venv\Scripts\python -m uvicorn app.main:app --port 8000"

echo [2/3] Starting document parse worker (Celery) ...
start "RAG-Worker" /d "%~dp0backend" cmd /k "title RAG-Worker && set PYTHONIOENCODING=utf-8 && .venv\Scripts\python -m celery -A app.workers.celery_app worker -P solo -l info"

echo [3/3] Starting frontend on port 5173 ...
start "RAG-Frontend" /d "%~dp0frontend" cmd /k "title RAG-Frontend && npm run dev"

echo.
echo Opening browser in 10 seconds: http://localhost:5173
timeout /t 10 /nobreak >nul
start http://localhost:5173

echo.
echo Admin login: admin / 123456  (top-right menu - Knowledge Base Admin)
echo Stop all services: run stop_dev.bat
pause
