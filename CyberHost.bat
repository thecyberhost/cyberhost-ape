@echo off
REM ===================================================================
REM  CyberHost APE - Android Pentesting Environment
REM  Double-click to launch the interactive console.
REM  Uses the BUNDLED Python runtime if present, else system Python.
REM ===================================================================
setlocal
set "CYBERHOST_HOME=%~dp0"
REM strip trailing backslash
if "%CYBERHOST_HOME:~-1%"=="\" set "CYBERHOST_HOME=%CYBERHOST_HOME:~0,-1%"

set "PYEXE=%CYBERHOST_HOME%\runtime\python\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

pushd "%CYBERHOST_HOME%"
"%PYEXE%" -m cyberhost %*
set "RC=%ERRORLEVEL%"
popd

if "%~1"=="" (
  echo.
  pause
)
endlocal & exit /b %RC%
