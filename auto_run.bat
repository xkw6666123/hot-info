@echo off
chcp 65001 >nul 2>&1
cd /d C:\Users\Kevin\WorkBuddy\2026-05-08-task-5\hot-info

echo [%date% %time%] start >> auto_run.log

git pull --ff-only origin main >> auto_run.log 2>&1

C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe generate_hot.py >> auto_run.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: generate_hot.py failed >> auto_run.log
    exit /b 1
)

C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe gen_js_data.py >> auto_run.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: gen_js_data.py failed >> auto_run.log
    exit /b 1
)

git add data.json data.js >> auto_run.log 2>&1
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "auto: update" >> auto_run.log 2>&1
    git push origin main >> auto_run.log 2>&1
    echo [%date% %time%] pushed to GitHub >> auto_run.log

    copy /Y data.js "C:\Users\Kevin\WorkBuddy\Claw\hot-site\data.js" >> auto_run.log 2>&1
    copy /Y data.json "C:\Users\Kevin\WorkBuddy\Claw\hot-site\data.json" >> auto_run.log 2>&1
    powershell -ExecutionPolicy Bypass -File "C:\Users\Kevin\WorkBuddy\Claw\hot-site\deploy.ps1" >> auto_run.log 2>&1
    echo [%date% %time%] deployed to Vercel >> auto_run.log
) else (
    echo [%date% %time%] no changes >> auto_run.log
)

echo [%date% %time%] done >> auto_run.log
