#!/usr/bin/env python3
"""每小时自动爬数据 → 推送 GitHub（替代 auto_run.bat，解决编码/路径问题）"""
import subprocess, sys, os, json, time
from datetime import datetime

WORK = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(WORK, "auto_run.log")
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
        return
    log(f"gen_js_data OK")

    # Step 4: 检查数据完整性
    try:
        data = json.load(open(os.path.join(WORK, "data.json"), encoding="utf-8-sig"))
        count = len(data.get("articles", []))
        log(f"articles: {count}")
        if count < 50:
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
