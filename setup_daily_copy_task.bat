@echo off
chcp 65001 >nul
rem ============================================================
rem   Register Windows Task Scheduler: daily 09:30 auto-run
rem   Usage: right-click this file -> Run as administrator
rem ============================================================

set TASK_NAME=HotInfoCopyDaily
set SCRIPT_PATH=D:\AI\hotinfo\hot-info-new\daily_copy_run.bat

if not exist "%SCRIPT_PATH%" (
    echo [ERROR] script not found: %SCRIPT_PATH%
    pause
    exit /b 1
)

rem /TR path has NO spaces, so simple quoting is enough (no inner escaped quotes needed)
schtasks /Create /F /TN "%TASK_NAME%" /TR "%SCRIPT_PATH%" /SC DAILY /ST 09:30

if errorlevel 1 (
    echo.
    echo [FAILED] schtasks /Create returned error %errorlevel%.
    echo Make sure you right-click and "Run as administrator" (UAC -> Yes).
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Task [%TASK_NAME%] created: runs daily at 09:30.
echo.
echo Manage commands (run in cmd):
echo   Query  : schtasks /Query /TN %TASK_NAME% /V
echo   Run now: schtasks /Run   /TN %TASK_NAME%
echo   Delete : schtasks /Delete /TN %TASK_NAME% /F
echo.
pause
