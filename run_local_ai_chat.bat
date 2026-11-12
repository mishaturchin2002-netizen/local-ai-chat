@echo off
setlocal EnableExtensions
title Local AI Chat

rem ============================================================
rem  Local AI Chat - launches the Streamlit chat UI for Ollama
rem  and opens the browser automatically.
rem ============================================================

set "APP_DIR=%~dp0"
pushd "%APP_DIR%" || goto :no_dir

set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
set "PORT=8501"
set "LOCAL_AI_CHAT_AUTOOPEN=1"

echo.
echo  ============================================
echo    Local AI Chat  -  local Ollama chat UI
echo  ============================================
echo.

rem ---------- 1. Python ----------
rem  The app ships with its own portable Python + Streamlit in .\runtime
set "PY="
if exist "%APP_DIR%runtime\python.exe" set "PY=%APP_DIR%runtime\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%APP_DIR%.venv\Scripts\python.exe" set "PY=%APP_DIR%.venv\Scripts\python.exe"
if not defined PY (
    where py >nul 2>&1 && set "PY=py"
)
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python not found. Install it from https://www.python.org/downloads/
    pause
    popd
    exit /b 1
)

rem ---------- 2. Streamlit dependency ----------
"%PY%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [setup] Installing Streamlit, one moment...
    "%PY%" -m pip install --upgrade pip >nul 2>&1
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Could not install Streamlit. Check your internet connection.
        pause
        popd
        exit /b 1
    )
)

rem ---------- 3. Ollama server ----------
set "OLLAMA_UP="
netstat -an 2>nul | find /I "127.0.0.1:11434" | find /I "LISTENING" >nul && set "OLLAMA_UP=1"

if not defined OLLAMA_UP (
    if exist "%OLLAMA_EXE%" (
        echo [ollama] Starting Ollama server...
        start "" /b "%OLLAMA_EXE%" serve
        ping -n 4 127.0.0.1 >nul
    ) else if exist "%ProgramFiles%\Ollama\ollama.exe" (
        echo [ollama] Starting Ollama server...
        start "" /b "%ProgramFiles%\Ollama\ollama.exe" serve
        ping -n 4 127.0.0.1 >nul
    ) else (
        echo [WARN] Ollama was not found. The chat will open but cannot answer.
        echo        Install it from https://ollama.com/download
        echo.
    )
)

rem ---------- 4. Streamlit server (browser opens via open_chat.ps1) ----------
netstat -an 2>nul | find /I "127.0.0.1:%PORT%" | find /I "LISTENING" >nul && (
    echo [chat] Chat is already running - opening the browser...
    start "" "http://localhost:%PORT%"
    ping -n 3 127.0.0.1 >nul
    popd
    exit /b 0
)

echo [chat] Starting server at http://localhost:%PORT% ...
echo        Close this window to stop the chat.
echo.

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%APP_DIR%open_chat.ps1"

"%PY%" -m streamlit run "%APP_DIR%app.py" ^
    --server.port %PORT% ^
    --server.address localhost ^
    --server.headless true ^
    --browser.gatherUsageStats false ^
    --server.fileWatcherType none ^
    --theme.base dark

echo.
echo [chat] Server stopped.
popd
endlocal
exit /b 0

:no_dir
echo [ERROR] Cannot open folder: %APP_DIR%
pause
exit /b 1
