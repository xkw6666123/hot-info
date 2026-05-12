#!/usr/bin/env python3
"""
视频 ASR 文案提取 + 简介生成
依赖：yt-dlp, ffmpeg, whisper (openai-whisper)
模型：whisper small (~461MB, 需手动下载一次)

用法：
  python asr_extract.py --test    测试单条（沙漠一之雕）
  python asr_extract.py --all     处理所有视频
  python asr_extract.py --bilibili 只处理B站视频
"""
import json, os, sys, subprocess, time, hashlib

PYTHON = sys.executable
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "C:/Users/Kevin/ffmpeg/ffmpeg-master-latest-win64-gpl-shared/bin/ffmpeg.exe"
TEMP_DIR = os.path.join(WORK_DIR, "asr_temp")

# 清除代理的环境变量
def clean_env():
    env = {**os.environ}
    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
        env.pop(k, None)
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def download_media(url, output_tmpl):
    """yt-dlp 下载音频/视频"""
    is_bilibili = "bilibili.com" in url
    fmt = "30280/30232/30216" if is_bilibili else "worstaudio/worst"
    
    cmd = [PYTHON, "-m", "yt_dlp", "-f", fmt,
           "--max-filesize", "50M", "--no-playlist", 
           "--no-check-certificates", "-o", output_tmpl, url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, 
                       env=clean_env(), encoding="utf-8", errors="replace")
    if r.returncode != 0:
        err = r.stderr[-300:] if r.stderr else str(r.returncode)
        raise Exception(f"下载失败: {err}")


def convert_wav(src, dst):
    """ffmpeg 转 16kHz 单声道 WAV"""
    cmd = [FFMPEG, "-y", "-i", src, "-ac", "1", "-ar", "16000", "-t", "180", dst]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       env=clean_env(), encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise Exception(f"转换失败")


def transcribe(wav_path):
    """Whisper ASR"""
    import whisper
    model = whisper.load_model("small")
    result = model.transcribe(wav_path, language="zh", fp16=False)
    return result["text"].strip()


def summarize(text, max_len=300):
    """简单摘要：取前3句"""
    if not text or len(text) < 20:
        return None
    sentences = [s.strip() for s in text.replace("。", "。\n").split("\n") if s.strip()]
    if len(sentences) <= 1:
        return text[:max_len]
    # 取前几句
    summary = "".join(sentences[:4])
    if len(summary) > max_len:
        summary = summary[:max_len] + "…"
    return summary


def process_one(url, vid):
    """处理单个视频"""
    os.makedirs(TEMP_DIR, exist_ok=True)
    base = os.path.join(TEMP_DIR, f"v{abs(hash(vid)) % 10000}")
    tmpl = base + ".%(ext)s"
    wav = base + ".wav"
    
    try:
        download_media(url, tmpl)
        # 找下载的文件
        actual = None
        for ext in [".m4a", ".mp4", ".webm", ".mp3", ".opus", ".aac", ".flac"]:
            if os.path.exists(base + ext):
                actual = base + ext
                break
        if not actual:
            for f in os.listdir(TEMP_DIR):
                fp = os.path.join(TEMP_DIR, f)
                if f.startswith(os.path.basename(base)) and os.path.isfile(fp):
                    actual = fp
                    break
        if not actual:
            raise Exception("找不到下载文件")
        
        print(f"   下载: {os.path.getsize(actual)/1024:.0f}KB", end=" ")
        
        convert_wav(actual, wav)
        print(f"→ WAV: {os.path.getsize(wav)/1024:.0f}KB", end=" ")
        
        text = transcribe(wav)
        print(f"→ ASR: {len(text)}字")
        
        summary = summarize(text)
        return summary, text
    
    finally:
        for f in [base + e for e in [".m4a", ".mp4", ".webm", ".mp3", 
                   ".opus", ".aac", ".flac", ".wav", ""]]:
            try: os.remove(f)
            except: pass


def main():
    if len(sys.argv) < 2 or "--help" in sys.argv:
        print(__doc__)
        return
    
    mode = sys.argv[1]
    
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d["articles"] if a.get("source") == "blogger"]
    
    if mode == "--test":
        target = [a for a in bloggers if a.get("blogger_name") == "沙漠一之雕"]
    elif mode == "--bilibili":
        target = [a for a in bloggers if "bilibili.com" in (a.get("url") or "")]
    elif mode == "--all":
        target = bloggers
    else:
        print(f"未知模式: {mode}")
        return
    
    print(f"\n{'='*50}")
    print(f"ASR 提取: {len(target)} 条视频")
    print(f"{'='*50}\n")
    
    updated = 0
    for i, v in enumerate(target):
        url = v.get("url", "")
        vid = str(v.get("id", ""))
        name = v.get("blogger_name", "")
        
        print(f"[{i+1}/{len(target)}] {name}", end=" ")
        
        if not url:
            print("(无URL)")
            continue
        
        if "bilibili.com" not in url:
            print("(抖音视频需TikHub API，跳过)")
            continue
        
        try:
            summary, full_text = process_one(url, vid)
            if summary and summary != v.get("content_intro", ""):
                # 生成完整简介：摘要 + 简短提示
                v["content_intro"] = summary
                updated += 1
                print(f"  ✅ 简介: {summary[:100]}...")
            else:
                print(f"  - 无变化")
        except Exception as e:
            print(f"\n  ❌ {e}")
        print()
    
    if updated > 0:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    
    print(f"{'='*50}")
    print(f"✅ {updated}/{len(target)} 条视频文案已更新")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
