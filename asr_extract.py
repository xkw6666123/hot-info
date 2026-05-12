#!/usr/bin/env python3
"""免费 ASR：Playwright 拦截音频 → ffmpeg下载 → Whisper → 摘要"""
import json, os, subprocess, time, whisper, re, sys

FFMPEG = "C:/Users/Kevin/ffmpeg/ffmpeg-master-latest-win64-gpl-shared/bin/ffmpeg.exe"
PCLI = "playwright-cli"
WORK = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(WORK, "asr_temp")
os.makedirs(TMP, exist_ok=True)

def get_audio_url(video_url):
    """Playwright 打开视频页，从网络请求中截获音频 URL"""
    # 清理
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} kill-all"], 
                   capture_output=True)
    
    # 打开页面
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} open \"{video_url}\""],
                   capture_output=True, timeout=30)
    time.sleep(6)
    
    # 获取网络请求列表
    r = subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} requests"],
                       capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
    
    # 找到 audio URL (media-audio-und-mp4a)
    for line in r.stdout.split("\n"):
        if "media-audio-und-mp4a" in line and "douyinvod.com" in line:
            # 提取 URL
            import urllib.parse
            parts = line.split("=>")
            for part in parts:
                if "douyinvod.com" in part and "media-audio" in part:
                    url = part.strip().split(" ")[-1].strip("[]")
                    # URL decode
                    url = urllib.parse.unquote(url)
                    return url
    
    # 如果没找到音频，找 video URL
    for line in r.stdout.split("\n"):
        if "media-video-avc1" in line and "douyinvod.com" in line:
            parts = line.split("=>")
            for part in parts:
                if "douyinvod.com" in part:
                    url = part.strip().split(" ")[-1].strip("[]")
                    url = urllib.parse.unquote(url)
                    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} close"], capture_output=True)
                    return url
    
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} close"], capture_output=True)
    return None

def download_asr(audio_url):
    """下载音频 → ASR → 摘要"""
    mp4 = os.path.join(TMP, "_pw.mp4")
    wav = os.path.join(TMP, "_pw.wav")
    
    # ffmpeg 下载
    subprocess.run([FFMPEG, "-y", "-i", audio_url, "-c", "copy", "-t", "180", mp4],
                   capture_output=True, timeout=60)
    if not os.path.exists(mp4) or os.path.getsize(mp4) < 1000:
        return ""
    
    # 转 WAV
    subprocess.run([FFMPEG, "-y", "-i", mp4, "-ac", "1", "-ar", "16000", "-t", "180", wav],
                   capture_output=True, timeout=30)
    
    # Whisper
    model = whisper.load_model("small")
    r = model.transcribe(wav, language="zh", fp16=False)
    text = r["text"].strip()
    
    for f in [mp4, wav]:
        try: os.remove(f)
        except: pass
    
    # 摘要
    events = re.split(r'(?=第[一二三四五六七八九十\d]+[件事个]|首先|另外|还有|接下来|最后|OK|下一件事)', text)
    if len(events) > 1:
        return "\n".join(f"  · {e.strip()[:80]}" for e in events[:6] if len(e.strip()) > 10)
    return text[:300]

def main():
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} kill-all"], capture_output=True)
    
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d["articles"] if a.get("source") == "blogger" and "douyin.com" in (a.get("url") or "")]
    
    print(f"\n🎉 免费 ASR: {len(bloggers)} 条视频\n")
    
    updated = 0
    for i, v in enumerate(bloggers):
        url = v.get("url", "")
        name = v.get("blogger_name", "")
        title = v.get("title", "")[:30]
        
        print(f"[{i+1}/{len(bloggers)}] {name} | {title}")
        
        try:
            audio_url = get_audio_url(url)
            if not audio_url:
                print(f"  ⚠️ 未截获音频")
                continue
            
            summary = download_asr(audio_url)
            if summary and summary != v.get("content_intro", ""):
                v["content_intro"] = summary
                updated += 1
                print(f"  ✅ {len(summary)}字")
            else:
                print(f"  skip")
        except Exception as e:
            print(f"  ❌ {e}")
        print()
    
    if updated:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        subprocess.run([sys.executable, "gen_js_data.py"], cwd=WORK)
    
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} kill-all"], capture_output=True)
    print(f"\n✅ {updated}/{len(bloggers)} 已更新")

if __name__ == "__main__":
    main()
