@echo off
chcp 65001 >nul
:: 创建 Windows 任务计划程序：每3小时运行一次 auto_run.bat
:: 需要以管理员身份运行
set TASK_NAME=HotInfoAutoUpdate
set SCRIPT_PATH=D:\AI\hotinfo\hot-info\auto_run.bat
set WORK_DIR=D:\AI\hotinfo\hot-info

if not exist "%SCRIPT_PATH%" (
    echo 错误：找不到 %SCRIPT_PATH%
    pause
    exit /b 1
)

schtasks /Create /TN "%TASK_NAME%" /TR "\"%SCRIPT_PATH%\"" /SC HOURLY /MO 3 /ST 00:30 /RL HIGHEST /F /NP /RU "%USERNAME%" /RP
if errorlevel 1 (
    echo 创建任务计划失败，请确认已以管理员身份运行
    pause
    exit /b 1
)

echo 任务计划 [%TASK_NAME%] 创建成功
pause
