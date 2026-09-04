@echo off
title RAG QA System Stopper
echo Stopping services ...

rem 1. close service windows by title
taskkill /F /FI "WINDOWTITLE eq RAG-Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq RAG-Worker" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq RAG-Frontend" >nul 2>&1

rem 2. fallback: kill backend/frontend by port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

rem 3. fallback: kill celery worker by command line
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { $_.CommandLine -like '*celery*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo.
echo Stopped: backend (8000), frontend (5173), worker.
echo Note: MySQL and Memurai are system services and stay running.
pause
