#!/usr/bin/env python3
"""
本地 ASR 流水线：
  1. douyin-transcribe Playwright 拦截 → 获取视频播放URL
  2. ffmpeg 下载音频
  3. 小米 MiMo ASR API 转文字
  4. 更新 data.json

需要: MIMO_API_KEY 环境变量
"""

import asyncio, json, os, sys, subprocess, re, shutil, base64, urllib.request, urllib.error, time

# ── 路径 ──
DT_PATH = r"D:\AI\2026-06-06-23-33-48\douyin-transcribe"
sys.path.insert(0, DT_PATH)
import server  # _get_douyin_video_object, _pick_url_for_transcription

PROJECT = os.path.dirname(os.path.abspath(__file__))
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
TEMP = os.path.join(PROJECT, "asr_temp")
os.makedirs(TEMP, exist_ok=True)

# ── MiMo ASR (复用 asr_extract.py 的实现) ──
MIMO_API_KEY = os.environ.get("MIMO_API_KEY")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"

def mimo_asr(audio_path: str, language: str = "zh") -> str:
    """小米 MiMo ASR API"""
    if not MIMO_API_KEY:
        raise RuntimeError("MIMO_API_KEY 未设置！请 export MIMO_API_KEY=xxx")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    if len(audio_bytes) < 1000:
        return ""

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    mime = "audio/wav" if audio_path.endswith(".wav") else "audio/mpeg"

    payload = json.dumps({
        "model": "mimo-v2.5-asr",
        "messages": [{
            "role": "user",
            "content": [{
                "type": "input_audio",
                "input_audio": {"data": f"data:{mime};base64,{audio_b64}"}
            }]
        }],
        "asr_options": {"language": language},
        "max_tokens": 3000,
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{MIMO_BASE_URL}/chat/completions",
                data=payload, headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = ""
            if result.get("choices") and result["choices"][0].get("message"):
                text = result["choices"][0]["message"].get("content", "")
            return text.strip()
        except Exception as e:
            if attempt < 2:
                print(f"    MiMo 重试 {attempt+2}/3: {e}")
                time.sleep(3)
            else:
                print(f"    MiMo 失败: {e}")
                return ""


# ── 文本清洗 ──
_NOISE = [
    r"互联网宗教.*?许可证", r"药品医疗.*?备案", r"网上有害信息举报",
    r"违法和不良.*?举报", r"算法推荐.*?举报", r"ICP备\d+", r"公网安备\d+",
    r"经营许可证", r"网络文化经营", r"^\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}",
    r"^因浏览器限制.*静音",
]

def _clean(text: str) -> str:
    if not text:
        return text
    lines = [l.strip() for l in text.split("\n")]
    clean = []
    for line in lines:
        if not line or len(line) < 2:
            continue
        if any(re.search(p, line) for p in _NOISE):
            continue
        clean.append(line)
    return "\n".join(clean).strip()


# ── 单视频处理 ──

async def process_one(aweme_id: str, url: str, tag: str = "") -> str:
    print(f"  [1/3] Playwright 拦截 {tag}...")
    video = await server._get_douyin_video_object(url)
    if not isinstance(video, dict):
        return ""

    dl_url = server._pick_url_for_transcription(video)
    if not dl_url:
        print(f"    ❌ 无下载URL")
        return ""
    print(f"    URL: {dl_url[:80]}...")

    print(f"  [2/3] ffmpeg 下载...")
    wav = os.path.join(TEMP, f"asr_{tag}.wav")
    cmd = [
        FFMPEG, "-y",
        "-headers", "Referer: https://www.douyin.com/\r\n",
        "-i", dl_url, "-ac", "1", "-ar", "16000", "-t", "180", wav,
    ]
    subprocess.run(cmd, capture_output=True, timeout=120)

    if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
        subprocess.run([FFMPEG, "-y", "-i", dl_url, "-ac", "1", "-ar", "16000", "-t", "180", wav],
                       capture_output=True, timeout=120)

    if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
        return ""
    print(f"    ✅ {os.path.getsize(wav)//1024}KB")

    print(f"  [3/3] MiMo ASR...")
    text = mimo_asr(wav)
    text = _clean(text)

    try:
        os.remove(wav)
    except:
        pass

    if len(text) < 20:
        print(f"    ⚠️ 过短 ({len(text)}字)")
        return ""

    chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    if chinese / max(len(text), 1) < 0.3:
        print(f"    ⚠️ 中文占比低 ({chinese}/{len(text)})")
        return ""

    print(f"    ✅ {len(text)}字: {text[:60]}...")
    return text[:5000]


# ── B站视频处理 ──

async def process_bilibili(url: str, tag: str = "") -> str:
    """B站视频：使用yt-dlp下载音频 + MiMo ASR"""
    import yt_dlp

    print(f"  [1/3] yt-dlp 下载音频 {tag}...")
    wav = os.path.join(TEMP, f"bili_{tag}.wav")

    # yt-dlp 配置（使用浏览器cookies绕过B站限制）
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': wav.replace('.wav', '.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '16',
        }],
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'cookiesfrombrowser': ('chrome',),  # 从Chrome读取cookies
        'download_ranges': lambda info, ydl: [{'start_time': 0, 'end_time': 180}],  # 只取前3分钟
        'force_keyframes_at_cuts': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"    ❌ yt-dlp 失败: {e}")
        return ""

    # 检查文件是否存在
    if not os.path.exists(wav):
        # 尝试查找其他格式
        for ext in ['wav', 'mp3', 'm4a', 'webm']:
            alt = wav.replace('.wav', f'.{ext}')
            if os.path.exists(alt):
                wav = alt
                break
        else:
            print(f"    ❌ 音频文件不存在")
            return ""

    file_size = os.path.getsize(wav)
    if file_size < 1000:
        print(f"    ❌ 音频文件过小: {file_size}字节")
        return ""
    print(f"    ✅ {file_size//1024}KB")

    # 转换为16kHz单声道（MiMo ASR要求）
    wav_16k = wav.replace('.wav', '_16k.wav')
    cmd = [FFMPEG, '-y', '-i', wav, '-ac', '1', '-ar', '16000', '-t', '180', wav_16k]
    subprocess.run(cmd, capture_output=True, timeout=60)
    if os.path.exists(wav_16k) and os.path.getsize(wav_16k) > 1000:
        wav = wav_16k
        print(f"    ✅ 转换为16kHz: {os.path.getsize(wav)//1024}KB")

    print(f"  [2/3] MiMo ASR...")
    text = mimo_asr(wav)
    text = _clean(text)

    # 清理临时文件
    try:
        os.remove(wav)
    except Exception:
        pass

    if len(text) < 20:
        print(f"    ⚠️ 过短 ({len(text)}字)")
        return ""

    chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    if chinese / max(len(text), 1) < 0.3:
        print(f"    ⚠️ 中文占比低 ({chinese}/{len(text)})")
        return ""

    print(f"    ✅ {len(text)}字: {text[:60]}...")
    return text[:5000]


# ── 主流程 ──

async def main():
    if not MIMO_API_KEY:
        print("❌ 请先设置 MIMO_API_KEY 环境变量")
        print("   export MIMO_API_KEY=your_key_here")
        return

    with open("data.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    bloggers = [a for a in data["articles"] if a.get("source") == "blogger"]
    need = [a for a in bloggers if len(a.get("content_intro", "")) < 500]

    print(f"\n🎯 本地 ASR (MiMo): {len(need)}/{len(bloggers)} 条\n")

    if not need:
        print("全部已有完整文案！")
        return

    updated = 0
    for i, v in enumerate(need):
        name = v.get("blogger_name", "")
        title = v.get("title", "")[:35]
        aweme_id = v.get("aweme_id", "")
        url = v.get("url", "")

        # 根据URL类型选择处理方式
        if "douyin.com" in url:
            # 抖音视频：使用Playwright拦截
            print(f"[{i+1}/{len(need)}] {name} | {title}")
            try:
                text = await process_one(aweme_id, url, tag=aweme_id or str(i))
                if text:
                    v["content_intro"] = text
                    updated += 1
            except Exception as e:
                print(f"    ❌ {type(e).__name__}: {e}")
            print()
        elif "bilibili.com" in url:
            # B站视频：使用yt-dlp下载音频 + ASR
            print(f"[{i+1}/{len(need)}] {name} | {title} [B站]")
            try:
                text = await process_bilibili(url, tag=str(i))
                if text:
                    v["content_intro"] = text
                    updated += 1
            except Exception as e:
                print(f"    ❌ {type(e).__name__}: {e}")
            print()

    if updated:
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        subprocess.run([sys.executable, "gen_js_data.py"], cwd=PROJECT)

    print(f"\n✅ 完成: {updated}/{len(need)} 条已更新")
    print(f"   git add data.json data.js index.html && git commit -m 'ASR: MiMo文案提取 ({updated}条)' && git push")


if __name__ == "__main__":
    asyncio.run(main())
