#!/usr/bin/env python3
"""
免费抖音下载方案：扫码登录 → 保存 cookies → yt-dlp 免费下载 → Whisper ASR
运行：python tools/free_douyin_asr.py
"""
import subprocess, os, time, json, sys

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(WORK, "douyin_cookies.txt")
COOKIE_JSON = os.path.join(WORK, "douyin_cookies.json")
ASR_TMP = os.path.join(WORK, "asr_temp")
PCLI = "playwright-cli"
FFMPEG = "C:/Users/Kevin/ffmpeg/ffmpeg-master-latest-win64-gpl-shared/bin/ffmpeg.exe"
PY = sys.executable
os.makedirs(ASR_TMP, exist_ok=True)

def step1_login():
    """第一步：打开浏览器扫码登录"""
    print("\n" + "=" * 50)
    print("  请在浏览器中扫码登录抖音（60秒）")
    print("=" * 50)
    
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} open https://www.douyin.com/"],
                   capture_output=True)
    time.sleep(3)
    
    for i in range(60, 0, -5):
        print(f"\r等待扫码... {i}秒 ", end="", flush=True)
        time.sleep(5)
    print()
    
    # 保存 cookies
    print("保存 cookies...")
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} state-save {COOKIE_JSON}"],
                   capture_output=True)
    
    with open(COOKIE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    
    cookies = data.get("cookies", [])
    dy_cookies = [c for c in cookies if "douyin" in c.get("domain", "")]
    
    with open(COOKIE_FILE, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in dy_cookies:
            f.write(f"{c['domain']}\tTRUE\t{c.get('path','/')}\t"
                   f"{'TRUE' if c.get('secure') else 'FALSE'}\t"
                   f"{int(c.get('expires',-1))}\t"
                   f"{c['name']}\t{c['value']}\n")
    
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} close"], capture_output=True)
    print(f"✅ 已保存 {len(dy_cookies)} 个抖音 cookies → {COOKIE_FILE}")

def step2_download(url, output_tmpl):
    """第二步：用 yt-dlp + cookies 下载视频"""
    env = {**os.environ}
    for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:
        env.pop(k, None)
    env['PYTHONIOENCODING'] = 'utf-8'
    
    r = subprocess.run([
        PY, "-m", "yt_dlp",
        "--cookies", COOKIE_FILE,
        "-f", "worstaudio/worst",
        "--max-filesize", "30M",
        "--no-playlist",
        "-o", output_tmpl,
        url
    ], capture_output=True, text=True, timeout=60, env=env, encoding="utf-8", errors="replace")
    
    if r.returncode == 0:
        for ext in [".m4a", ".mp4", ".webm", ".mp3"]:
            p = output_tmpl.replace("%(ext)s", ext[1:])
            if os.path.exists(p) and os.path.getsize(p) > 1000:
                return p
        # 找无扩展名的文件
        base = output_tmpl.replace(".%(ext)s", "")
        for f in os.listdir(os.path.dirname(base)):
            fp = os.path.join(os.path.dirname(base), f)
            if f.startswith(os.path.basename(base)) and os.path.getsize(fp) > 1000:
                return fp
    return None

def step3_asr(media_path):
    """第三步：Whisper ASR"""
    wav = media_path + ".wav"
    subprocess.run([FFMPEG, "-y", "-i", media_path, "-ac", "1", "-ar", "16000",
                    "-t", "180", wav], capture_output=True)
    if not os.path.exists(wav):
        return ""
    
    import whisper
    model = whisper.load_model("small")
    r = model.transcribe(wav, language="zh", fp16=False)
    text = r["text"].strip()
    
    try: os.remove(wav)
    except: pass
    try: os.remove(media_path)
    except: pass
    
    # 简单摘要
    import re
    events = re.split(r'(?=第[一二三四五六七八九十\d]+[件事个]|首先|另外|还有|接下来|最后)', text)
    if len(events) > 1:
        return "\n".join(f"  · {e.strip()[:80]}" for e in events[:5] if e.strip())
    return text[:300]

def step4_process_all():
    """处理所有抖音视频"""
    with open(os.path.join(WORK, "data.json"), "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d["articles"] if a.get("source") == "blogger" 
                and "douyin.com" in (a.get("url") or "")]
    
    print(f"\n{'='*50}")
    print(f"  免费 ASR: {len(bloggers)} 条抖音视频")
    print(f"{'='*50}\n")
    
    updated = 0
    for i, v in enumerate(bloggers):
        url = v.get("url", "")
        name = v.get("blogger_name", "")
        vid = str(v.get("id", ""))
        tmpl = os.path.join(ASR_TMP, f"free_{vid}.%(ext)s")
        
        print(f"[{i+1}/{len(bloggers)}] {name}\n  ⏳ 下载...", end=" ", flush=True)
        media = step2_download(url, tmpl)
        
        if not media:
            print("❌ 下载失败")
            continue
        
        print(f"{os.path.getsize(media)/1024:.0f}KB → ASR...", end=" ", flush=True)
        text = step3_asr(media)
        
        if text and len(text) > 10:
            if text != v.get("content_intro", ""):
                v["content_intro"] = text
                updated += 1
                print(f"✅ {len(text)}字")
        else:
            print("⚠️ 无有效语音")
    
    if updated:
        with open(os.path.join(WORK, "data.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        subprocess.run([PY, "gen_js_data.py"], cwd=WORK)
    
    print(f"\n✅ {updated} 条已更新")

if __name__ == "__main__":
    if not os.path.exists(COOKIE_FILE):
        step1_login()
    
    # 测试 cookies 是否有效
    test = step2_download(
        "https://www.douyin.com/video/7637886711091793081",
        os.path.join(ASR_TMP, "cookie_test.%(ext)s")
    )
    if test:
        print("✅ Cookies 有效！开始处理所有视频...")
        os.remove(test)  # 清理测试文件
        step4_process_all()
    else:
        print("❌ Cookies 失效，重新登录...")
        os.remove(COOKIE_FILE)
        step1_login()
        # 递归重试
        print("请重新运行此脚本")
