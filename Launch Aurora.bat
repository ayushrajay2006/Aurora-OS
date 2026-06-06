@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%\.venv\Scripts\pythonw.exe" (
    start "" "%ROOT%\.venv\Scripts\pythonw.exe" "%ROOT%\main.py"
    exit /b 0
)

if exist "%ROOT%\.venv\Scripts\python.exe" (
    start "" "%ROOT%\.venv\Scripts\python.exe" "%ROOT%\main.py"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%ROOT%\main.py"
    exit /b 0
)

start "" python "%ROOT%\main.py"
exit /b 0
