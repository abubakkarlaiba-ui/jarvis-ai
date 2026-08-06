@echo off
REM JARVIS AI Assistant — Startup Script (Windows)
REM =================================================
REM Usage:
REM   start.bat              Start in default mode (terminal + API)
REM   start.bat --mode api   Start API server only
REM   start.bat --mode terminal   Start terminal UI only
REM   start.bat --debug      Start with debug logging

setlocal

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

cd /d "%PROJECT_DIR%"

REM Create .env if it doesn't exist
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo Please edit .env with your API keys before running.
    exit /b 1
)

REM Ensure data directories exist
if not exist data\logs mkdir data\logs
if not exist data\vector_store mkdir data\vector_store
if not exist data\models mkdir data\models
if not exist data\knowledge mkdir data\knowledge
if not exist plugins mkdir plugins

REM Activate virtual environment if present
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install dependencies if needed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo Starting JARVIS...
python -m jarvis %*

endlocal
