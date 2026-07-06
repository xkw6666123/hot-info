@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
cd /d D:\AI\hotinfo\hot-info

echo [%date% %time%] start >> auto_run.log

:: ========== 直连GitHub：清除代理环境变量 ==========
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set ALL_PROXY=
set all_proxy=

git pull --ff-only origin main >> auto_run.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARNING: git pull failed, continuing with local data >> auto_run.log
)

:: 归档当前数据（防止丢失）
C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe data_archive.py >> auto_run.log 2>&1

C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe generate_hot.py --local >> auto_run.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: generate_hot.py failed >> auto_run.log
    exit /b 1
)

:: 从归档恢复历史数据
C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe data_archive.py restore >> auto_run.log 2>&1

:: 数据合并保护：确保不丢失博主数据和灵感库
C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe merge_data.py >> auto_run.log 2>&1

:: 自动ASR：检测缺失文案并自动补提
set MIMO_API_KEY=
C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe auto_asr.py >> auto_run.log 2>&1

:: 持续学习：归档文案 + 学习风格
C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe continuous_learner.py >> auto_run.log 2>&1

C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe gen_js_data.py >> auto_run.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: gen_js_data.py failed >> auto_run.log
    exit /b 1
)

:: 检查数据完整性（至少 50 条文章 + 博主数据 + 灵感库）
for /f %%i in ('C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe -c "import json;d=json.load(open('data.json',encoding='utf-8-sig'));print(len(d.get('articles',[])))"') do set ART_COUNT=%%i
for /f %%i in ('C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe -c "import json;d=json.load(open('data.json',encoding='utf-8-sig'));print(len([a for a in d.get('articles',[]) if a.get('source')=='blogger']))"') do set BLOG_COUNT=%%i
for /f %%i in ('C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe -c "import json;d=json.load(open('data.json',encoding='utf-8-sig'));print(len(d.get('inspirations',[])))"') do set INSP_COUNT=%%i
echo [%date% %time%] articles: %ART_COUNT%, bloggers: %BLOG_COUNT%, inspirations: %INSP_COUNT% >> auto_run.log
if %ART_COUNT% LSS 50 (
    echo [%date% %time%] WARNING: only %ART_COUNT% articles, skipping push >> auto_run.log
    exit /b 1
)

git add data.json data.js index.html asr_content.json blogger_content_archive.json deep_style_learned.json data_archive.json >> auto_run.log 2>&1
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "auto: update (local)" >> auto_run.log 2>&1
    git push origin main >> auto_run.log 2>&1
    echo [%date% %time%] pushed to GitHub >> auto_run.log
) else (
    echo [%date% %time%] no changes >> auto_run.log
)

echo [%date% %time%] done >> auto_run.log
