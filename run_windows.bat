@echo off
REM This script starts the FastAPI application on Windows

REM Load environment variables from .env file if it exists
if exist backend\.env (
    for /f "usebackq tokens=*" %%a in ("backend\.env") do (
        set %%a
    )
)

REM Use environment variables for host and port, with defaults
if not defined HOST set HOST=0.0.0.0
if not defined PORT set PORT=8000

set RELOAD_FLAG=
if /i "%UVICORN_RELOAD%"=="true" set RELOAD_FLAG=--reload

echo Attempting to start server on %HOST%:%PORT% with reload flag: '%RELOAD_FLAG%'

REM Start the uvicorn server
python -m uvicorn backend.app.main:app --host %HOST% --port %PORT% %RELOAD_FLAG%