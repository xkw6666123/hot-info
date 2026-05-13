#!/usr/bin/env python3
"""每3小时自动爬数据 → 推送 GitHub（替代 auto_run.bat，解决编码/路径问题）"""
import subprocess, sys, os, json, time
from datetime import datetime

WORK = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(WORK, "auto_run.log")
# 显式指定 Python 路径，避免 Windows Store 假 Python 覆盖
PYTHON = r"C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe"
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run(cmd, timeout=120, cwd=WORK, use_proxy=False):
    """运行命令。use_proxy=True 时保留/设置代理（git push 用），否则清代理（爬虫直连国内）"""
    env = os.environ.copy()
    if use_proxy:
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            if k not in env or not env[k]:
                env[k] = "http://127.0.0.1:10809"
    else:
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
            env.pop(k, None)
    # 强制 UTF-8 输出
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env, 
                          encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)

def main():
    log("start")

    # Step 1: git pull（需要代理连 GitHub）
    code, out = run(["git", "pull", "--ff-only", "origin", "main"], timeout=30, use_proxy=True)
    if code != 0:
        log(f"WARNING: git pull failed: {out[:200]}")
    else:
        log(f"git pull OK")

    # Step 2: generate_hot.py
    code, out = run([PYTHON, "generate_hot.py", "--local"], timeout=180)
    if code != 0:
        log(f"ERROR: generate_hot.py failed: {out[:200]}")
        sys.exit(1)
    log(f"generate_hot OK ({out.strip()[-100:]})")

    # Step 3: gen_js_data.py
    code, out = run([PYTHON, "gen_js_data.py"], timeout=30)
    if code != 0:
        log(f"ERROR: gen_js_data.py failed: {out[:200]}")
        sys.exit(1)
    log(f"gen_js_data OK")

    # Step 3.5: 从视频描述生成 content_intro（描述 → 文案，仅填充无真实转录的）
    try:
        code_gci, out_gci = run([PYTHON, "gen_content_intro.py"], timeout=60)
        if code_gci == 0:
            log("gen_content_intro OK")
    except Exception as e:
        log(f"WARNING: gen_content_intro failed: {e}")

    # Step 4: ASR 提取博主视频真实文案
    # 触发条件：content_intro 为空/过短/被污染
    try:
        import re
        data = json.load(open(os.path.join(WORK, "data.json"), encoding="utf-8-sig"))
        garbage_re = re.compile(r'互联网宗教|备案|许可证|网上有害|不良信息举报')
        need_asr = []
        for a in data.get("articles", []):
            if a.get("source") != "blogger":
                continue
            ci = a.get("content_intro", "")
            if len(ci) < 50 or garbage_re.search(ci):
                need_asr.append(a)
        if need_asr:
            bloggers_need = set(a.get("blogger_name", "") for a in need_asr)
            log(f"ASR needed for {len(need_asr)} videos: {bloggers_need}")
            code, out = run([PYTHON, "asr_extract.py"], timeout=600)
            if code != 0:
                log(f"WARNING: ASR failed: {out[:200]}")
            else:
                log(f"ASR OK")
                code2, out2 = run([PYTHON, "gen_js_data.py"], timeout=30)
                if code2 != 0:
                    log(f"ERROR: gen_js_data re-run failed: {out2[:200]}")
        else:
            log("all videos have clean content_intro, no ASR needed")
    except Exception as e:
        log(f"WARNING: ASR check failed: {e}")

    # Step 5: 检查数据完整性
    try:
        data = json.load(open(os.path.join(WORK, "data.json"), encoding="utf-8-sig"))
        count = len(data.get("articles", []))
        log(f"articles: {count}")
        if count < 30:
            log(f"WARNING: only {count} articles, skipping push")
            return
    except Exception as e:
        log(f"ERROR: can't read data.json: {e}")
        return

    # Step 5: git commit & push（需要代理）
    code, _ = run(["git", "add", "data.json", "data.js", "index.html"], timeout=10, use_proxy=True)
    code2, diff = run(["git", "diff", "--cached", "--stat"], timeout=10, use_proxy=True)
    
    if "file changed" in diff or "files changed" in diff:
        code3, out3 = run(["git", "commit", "-m", "auto: update (local)"], timeout=10, use_proxy=True)
        code4, out4 = run(["git", "push", "origin", "main"], timeout=60, use_proxy=True)
        if code4 != 0:
            log(f"ERROR: git push failed: {out4[:200]}")
        else:
            log("pushed to GitHub")
    else:
        log("no changes")

    log("done")

if __name__ == "__main__":
    main()
