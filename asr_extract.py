#!/usr/bin/env python3
"""
视频 ASR 文案提取 + 简介生成
- B站: yt-dlp 直接下载
- 抖音: TikHub API 获取下载链接 → ffmpeg 下载
- ASR: Whisper small
"""
import json, os, sys, subprocess, time, urllib.request

PYTHON = sys.executable
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "C:/Users/Kevin/ffmpeg/ffmpeg-master-latest-win64-gpl-shared/bin/ffmpeg.exe"
TEMP_DIR = os.path.join(WORK_DIR, "asr_temp")

# TikHub API 配置
TIKHUB_KEY = "srAlG/ROjGy6h0XKAoib+DTMbQKKX6Ns/SbJvkumTaW8jVOVPVyHSROeOw=="
TIKHUB_BASE = "https://api.tikhub.io"


def tikhub_get(endpoint):
    """TikHub API 调用（走系统代理）"""
    url = f"{TIKHUB_BASE}{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TIKHUB_KEY}"})
    # 使用系统代理（127.0.0.1:10809）
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def get_douyin_download_url(video_page_url):
    """通过 TikHub 获取抖音视频的下载链接（需要代理）"""
    # 从 video_page_url 提取 aweme_id
    # URL 格式: https://www.douyin.com/video/7637886711091793081
    import re
    m = re.search(r'/video/(\d+)', video_page_url)
    if not m:
        return None
    aweme_id = m.group(1)
    
    try:
        # 方式1: 尝试直接搜索用户来获取视频
        # 先从视频ID推测需要搜索的用户...
        # 其实最快的方式是用 share link parse
        data = tikhub_get(f"/api/v1/douyin/data/parsing/share_link?share_text={video_page_url}")
        print(f"    TikHub share parse: OK" if data.get("code") == 200 else f"    TikHub: {str(data)[:200]}")
    except Exception as e:
        print(f"    TikHub share error: {e}")
        return None
    
    # 从响应中提取视频信息
    # TikHub 返回格式可能在 data.data 或直接 data 中
    video_data = None
    for path in [
        lambda d: d.get("data", {}).get("data", {}),
        lambda d: d.get("data", {}),
    ]:
        try:
            inner = path(data)
            if inner and (inner.get("aweme_detail") or inner.get("video")):
                video_data = inner
                break
        except:
            pass
    
    if video_data:
        aweme = video_data.get("aweme_detail", video_data)
        video = aweme.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        if url_list:
            return url_list[0]
    
    return None


def download_douyin_via_ffmpeg(video_url, output_path):
    """通过 ffmpeg 下载抖音视频（m3u8流）"""
    cmd = [FFMPEG, "-y", "-i", video_url, 
           "-c", "copy", "-t", "180", "-max_muxing_queue_size", "1024",
           output_path]
    env = {**os.environ}
    for k in ['PYTHONIOENCODING']: pass
    env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env,
                       encoding="utf-8", errors="replace")
    return r.returncode == 0


def download_bilibili(url, output_tmpl):
    """yt-dlp 下载 B站音频"""
    cmd = [PYTHON, "-m", "yt_dlp", "-f", "30232",
           "--max-filesize", "50M", "--no-playlist",
           "--no-check-certificates", "-o", output_tmpl, url]
    env = {**os.environ}
    for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy']:
        env.pop(k, None)
    env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise Exception(f"下载失败")


def convert_wav(src, dst):
    """转 16kHz WAV"""
    cmd = [FFMPEG, "-y", "-i", src, "-ac", "1", "-ar", "16000", "-t", "180", dst]
    subprocess.run(cmd, capture_output=True, timeout=30, encoding="utf-8", errors="replace")


def transcribe(wav_path):
    """Whisper ASR"""
    import whisper
    model = whisper.load_model("small")
    result = model.transcribe(wav_path, language="zh", fp16=False)
    return result["text"].strip()


def summarize(text):
    """截取前4句作摘要"""
    if not text or len(text) < 20: return None
    sentences = [s.strip() for s in text.replace("。", "。\n").split("\n") if s.strip()]
    summary = "。".join(sentences[:4])
    return summary[:400]


def process_one(v):
    """处理单个视频，返回 content_intro"""
    url = v.get("url", "")
    vid = str(v.get("id", ""))
    name = v.get("blogger_name", "")
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    base = os.path.join(TEMP_DIR, f"v{abs(hash(vid))%10000}")
    wav = base + ".wav"
    
    is_bilibili = "bilibili.com" in url
    is_douyin = "douyin.com" in url
    
    # 下载
    media_file = None
    if is_bilibili:
        tmpl = base + ".%(ext)s"
        download_bilibili(url, tmpl)
        for ext in [".m4a", ".mp3", ".webm"]:
            if os.path.exists(base + ext):
                media_file = base + ext
                break
    elif is_douyin:
        dl_url = get_douyin_download_url(url)
        if not dl_url:
            print("    ❌ 无法获取抖音下载链接（检查代理）")
            return None
        mp4 = base + ".mp4"
        ok = download_douyin_via_ffmpeg(dl_url, mp4)
        if ok and os.path.exists(mp4) and os.path.getsize(mp4) > 1000:
            media_file = mp4
        else:
            print("    ❌ 抖音视频下载失败")
            return None
    
    if not media_file:
        print("    ❌ 媒体文件不存在")
        return None
    
    # 转 WAV + ASR
    convert_wav(media_file, wav)
    text = transcribe(wav)
    summary = summarize(text)
    
    # 清理
    for f in [media_file, wav]:
        try: os.remove(f)
        except: pass
    
    return summary or text[:300]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--help"
    
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d["articles"] if a.get("source") == "blogger"]
    
    if mode == "--all":
        target = bloggers
    elif mode == "--bilibili":
        target = [a for a in bloggers if "bilibili.com" in (a.get("url") or "")]
    elif mode == "--douyin":
        target = [a for a in bloggers if "douyin.com" in (a.get("url") or "")]
    else:
        target = [a for a in bloggers if a.get("blogger_name") == "沙漠一之雕"]
    
    print(f"\nASR {mode}: {len(target)} 条视频\n")
    
    updated = 0
    for i, v in enumerate(target):
        url = v.get("url", "")
        name = v.get("blogger_name", "")
        print(f"[{i+1}/{len(target)}] {name}", end=" ")
        
        try:
            intro = process_one(v)
            if intro and intro != v.get("content_intro", ""):
                v["content_intro"] = intro
                updated += 1
                print(f"✅ {len(intro)}字: {intro[:100]}...")
            else:
                print("⏭️ 无变化或失败")
        except Exception as e:
            print(f"❌ {e}")
        print()
    
    if updated:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        subprocess.run([PYTHON, "gen_js_data.py"], cwd=WORK_DIR)
        print(f"✅ {updated} 条已更新，data.js 已刷新")
    else:
        print("无更新")

if __name__ == "__main__":
    main()
