@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

rem ============================================================
rem   Copywriting Fetcher - daily task (invoked by Windows Task Scheduler)
rem   Only does "copywriting": Douyin+Bilibili blogger videos + ASR transcript + build + push
rem   Does NOT touch "news" (news is maintained by GitHub Actions every 3 hours)
rem ============================================================

rem script directory = hot-info-new, path-independent
cd /d "%~dp0"

set PY=C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe
rem ffmpeg is NOT in system PATH, add it explicitly (ASR audio transcoding needs it)
set PATH=C:\Users\Kevin\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin;%PATH%

set LOG=daily_copy_run.log
echo [%date% %time%] ===== Copywriting Fetcher DAILY START ===== >> %LOG%

rem clear proxy (git direct to GitHub + domestic platforms direct)
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set ALL_PROXY=
set all_proxy=

rem 1. sync remote (news is maintained by CI, pull latest, failure is non-fatal)
git pull --ff-only origin main >> %LOG% 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARNING: git pull failed, continue with local data >> %LOG%
)

rem 2. fetch blogger videos (copywriting source: Douyin+Bilibili bloggers; --remote runs only bloggers, NOT news)
%PY% generate_hot.py --remote >> %LOG% 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: generate_hot.py --remote failed >> %LOG%
    exit /b 1
)

rem 3. ASR transcribe blogger videos -> real copywriting (Douyin+Bilibili no-login download, funasr cached model)
%PY% whisper_asr_local.py >> %LOG% 2>&1

rem 3.5 accumulate ASR transcripts into asr_content.json (continuous learning material for LLM)
%PY% merge_data.py >> %LOG% 2>&1

rem 3.6 re-learn blogger style fingerprints (catchphrases/openings/endings) from the growing archive
%PY% -c "import deep_style_learner as d; d.learn_all_styles_deep()" >> %LOG% 2>&1

rem 4. rebuild data.js / inspiration.js / index.html (so real copywriting takes effect)
%PY% gen_js_data.py >> %LOG% 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: gen_js_data.py failed >> %LOG%
    exit /b 1
)

rem 5. commit and push to GitHub (triggers Cloudflare Pages auto-deploy)
git add data.json data.js inspiration.js index.html asr_content.json >> %LOG% 2>&1
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "auto: copywriting update (daily)" >> %LOG% 2>&1
    git push origin main >> %LOG% 2>&1
    if errorlevel 1 (
        echo [%date% %time%] WARNING: git push failed (maybe CI concurrent push), will retry next run >> %LOG%
    ) else (
        echo [%date% %time%] pushed to GitHub >> %LOG%
    )
) else (
    echo [%date% %time%] no changes, skip push >> %LOG%
)

echo [%date% %time%] ===== Copywriting Fetcher DAILY END ===== >> %LOG%
