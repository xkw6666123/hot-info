#!/usr/bin/env python3
"""
单视频 ASR：Playwright 抓音频 → ffmpeg 转小 mp3 → MiMo ASR
每个视频独立会话，完整清理
"""
import sys, os, json, time, subprocess, tempfile, urllib.request

SCRIPT = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT)
sys.path.insert(0, SCRIPT)
sys.stdout.reconfigure(line_buffering=True)

from asr_extract import mimo_asr, _clean_text

PCLI = "playwright-cli"
FFMPEG = "ffmpeg"
TEMP = os.path.join(SCRIPT, "asr_temp")
os.makedirs(TEMP, exist_ok=True)

def run(cmd, timeout=30):
    """安全运行命令"""
    try:
        r = subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {cmd}"],
                          capture_output=True, text=True, timeout=timeout)
        return r
    except:
        return None

def cleanup():
    run(f"{PCLI} close", 5)
    run(f"{PCLI} kill-all", 5)
    time.sleep(2)

def process_one(aweme_id, blogger_name):
    """处理单个视频"""
    url = f"https://www.douyin.com/video/{aweme_id}"
    print(f"  [{blogger_name}] {url}", flush=True)
    
    # 完整清理
    cleanup()
    
    # 1. 打开视频页
    print("  Opening page...", flush=True)
    for attempt in range(2):
        r = run(f'{PCLI} open "{url}"', timeout=30)
        if r and r.returncode == 0:
            break
        if attempt == 0:
            cleanup()
    else:
        print("  FAIL: cannot open page"); return None
    
    time.sleep(10)  # 等待视频加载
    
    # 2. 点击页面触发播放
    run(f'{PCLI} click "e1"', timeout=5)
    time.sleep(5)
    
    # 3. 获取网络请求
    print("  Capturing requests...", flush=True)
    r = run(f"{PCLI} requests", timeout=20)
    if not r or not r.stdout:
        print("  FAIL: no requests"); cleanup(); return None
    
    # 4. 找音频 URL
    audio_url = None
    for line in r.stdout.split("\n"):
        if "media-audio-und-mp4a" in line and "douyinvod.com" in line:
            import urllib.parse
            parts = line.split("=>")
            for part in parts:
                if "douyinvod.com" in part:
                    audio_url = urllib.parse.unquote(part.strip().split(" ")[-1].strip("[]"))
                    break
        if audio_url:
            break
    
    if not audio_url:
        print("  FAIL: no audio URL found"); cleanup(); return None
    
    print(f"  Audio URL found", flush=True)
    
    # 5. 关闭 Playwright
    cleanup()
    
    # 6. 下载音频（小尺寸）
    mp3_path = os.path.join(TEMP, f"{aweme_id}.mp3")
    print("  Downloading audio...", flush=True)
    r = subprocess.run([
        FFMPEG, "-y",
        "-headers", "Referer: https://www.douyin.com/\r\n",
        "-i", audio_url,
        "-t", "90", "-vn", "-ac", "1", "-ar", "16000",
        "-b:a", "24k", "-acodec", "libmp3lame",
        mp3_path
    ], capture_output=True, text=True, timeout=60)
    
    if r.returncode != 0 or not os.path.exists(mp3_path):
        err = (r.stderr or "")[-200:]
        print(f"  FAIL: ffmpeg download error: {err}"); return None
    
    sz_kb = os.path.getsize(mp3_path) // 1024
    print(f"  Audio: {sz_kb}KB", flush=True)
    
    # 7. MiMo ASR
    if sz_kb < 5:
        print("  FAIL: audio too small"); os.remove(mp3_path); return None
    
    print("  MiMo ASR...", flush=True)
    try:
        text = mimo_asr(mp3_path)
        os.remove(mp3_path)
        if text and len(text) > 30:
            return text
        else:
            print(f"  FAIL: ASR returned empty/short ({len(text) if text else 0} chars)")
            return None
    except Exception as e:
        print(f"  FAIL: MiMo error: {e}")
        if os.path.exists(mp3_path): os.remove(mp3_path)
        return None

# Main
print("Reading data...")
with open("data.json", "r", encoding="utf-8-sig") as f:
    d = json.load(f)

# 找需要 ASR 的视频
need = []
for a in d["articles"]:
    if a.get("source") != "blogger":
        continue
    if "douyin.com" not in (a.get("url") or ""):
        continue
    if len(a.get("content_intro", "")) >= 80:
        continue
    need.append(a)

if not need:
    print("All done!")
    sys.exit(0)

print(f"Videos needing ASR: {len(need)}")
updated = 0
failed = 0

for i, a in enumerate(need):
    print(f"\n[{i+1}/{len(need)}]", flush=True)
    t0 = time.time()
    text = process_one(a["aweme_id"], a["blogger_name"])
    elapsed = time.time() - t0
    
    if text:
        a["content_intro"] = _clean_text(text[:2000])
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"  DONE: {len(a['content_intro'])} chars in {elapsed:.0f}s", flush=True)
        updated += 1
    else:
        print(f"  FAILED after {elapsed:.0f}s", flush=True)
        failed += 1

cleanup()
print(f"\nDone! {updated} updated, {failed} failed")
