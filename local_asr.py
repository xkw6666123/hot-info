#!/usr/bin/env python3
"""
本地/CI 通用 ASR 流水线：
  1. douyin-transcribe Playwright 拦截 → 获取视频播放URL（仅本机，CI 自动跳过）
  2. ffmpeg 下载音频（B站走 yt-dlp）
  3. 转写引擎自动选择：有 MIMO_API_KEY 用小米 MiMo ASR；否则本地 whisper base
  4. 更新 data.json

环境变量: MIMO_API_KEY（可选；缺失时自动降级 whisper）
"""

import asyncio, json, os, sys, subprocess, re, shutil, base64, urllib.request, urllib.error, time

# ── 路径（douyin-transcribe 仅本机存在；CI 不存在时抖音视频优雅跳过，不再整体崩溃）──
DT_PATH = r"D:\AI\hotinfo\douyin-transcribe"
if os.path.isdir(DT_PATH):
    sys.path.insert(0, DT_PATH)
try:
    import server  # _get_douyin_video_object, _pick_url_for_transcription
except Exception:
    server = None

PROJECT = os.path.dirname(os.path.abspath(__file__))
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
TEMP = os.path.join(PROJECT, "asr_temp")
os.makedirs(TEMP, exist_ok=True)

# ── 转写引擎：MiMo 优先，whisper 兜底 ──
MIMO_API_KEY = os.environ.get("MIMO_API_KEY")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"

_WHISPER_MODEL = None

def whisper_asr(audio_path: str) -> str:
    """本地 whisper base（CPU 可跑，无需任何 API key）"""
    global _WHISPER_MODEL
    try:
        import whisper
    except ImportError:
        return ""
    if _WHISPER_MODEL is None:
        print("    ⏳ 加载 whisper base 模型...")
        _WHISPER_MODEL = whisper.load_model("base")
    r = _WHISPER_MODEL.transcribe(audio_path, language="zh", fp16=False,
                                  initial_prompt="以下是简体中文口语视频文案。",
                                  condition_on_previous_text=False)
    text = (r.get("text") or "").strip()
    try:
        from opencc import OpenCC
        text = OpenCC("t2s").convert(text)
    except Exception:
        pass
    return text

def mimo_asr(audio_path: str, language: str = "zh") -> str:
    """小米 MiMo ASR API"""
    if not MIMO_API_KEY:
        return ""

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


def transcribe(wav_path: str) -> str:
    """统一转写入口：MiMo 优先（有 key 时），whisper 兜底；返回清洗后文本"""
    text = ""
    if MIMO_API_KEY:
        text = mimo_asr(wav_path)
    if not text:
        text = whisper_asr(wav_path)
    return _clean(text or "")


# ── 单视频处理 ──

async def process_one(aweme_id: str, url: str, tag: str = "") -> str:
    if server is None:
        print(f"    ⏭️ douyin-transcribe 不可用（非本机环境），跳过抖音")
        return ""
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
        "-i", dl_url, "-ac", "1", "-ar", "16000", "-t", "300", wav,
    ]
    subprocess.run(cmd, capture_output=True, timeout=120)

    if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
        subprocess.run([FFMPEG, "-y", "-i", dl_url, "-ac", "1", "-ar", "16000", "-t", "300", wav],
                       capture_output=True, timeout=120)

    if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
        return ""
    print(f"    ✅ {os.path.getsize(wav)//1024}KB")

    print(f"  [3/3] ASR 转写...")
    text = transcribe(wav)

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
    """B站视频：使用yt-dlp下载音频 + ASR（CI无Chrome时自动免cookie）"""
    import yt_dlp

    print(f"  [1/3] yt-dlp 下载音频 {tag}...")
    wav = os.path.join(TEMP, f"bili_{tag}.wav")

    # yt-dlp 配置（本机用Chrome cookies绕过B站限制；CI无浏览器则免cookie直连）
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
        'download_ranges': lambda info, ydl: [{'start_time': 0, 'end_time': 300}],  # 取前5分钟
        'force_keyframes_at_cuts': True,
    }
    if not os.environ.get("CI") and not os.environ.get("GITHUB_ACTIONS"):
        ydl_opts['cookiesfrombrowser'] = ('chrome',)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"    ❌ yt-dlp 失败: {e}")
        # 兜底：去掉 postprocessor 与 cookie 再试一次（裸下载）
        if ydl_opts.get('cookiesfrombrowser'):
            ydl_opts.pop('cookiesfrombrowser', None)
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e2:
                print(f"    ❌ 免cookie重试仍失败: {e2}")
                return ""
        else:
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
    cmd = [FFMPEG, '-y', '-i', wav, '-ac', '1', '-ar', '16000', '-t', '300', wav_16k]
    subprocess.run(cmd, capture_output=True, timeout=60)
    if os.path.exists(wav_16k) and os.path.getsize(wav_16k) > 1000:
        wav = wav_16k
        print(f"    ✅ 转换为16kHz: {os.path.getsize(wav)//1024}KB")

    print(f"  [2/3] ASR 转写...")
    text = transcribe(wav)

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
    engine = "MiMo API" if MIMO_API_KEY else "whisper base(本地)"
    print(f"🎙️ 转写引擎: {engine}")

    with open("data.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    bloggers = [a for a in data["articles"] if a.get("source") == "blogger"]
    need = [a for a in bloggers if len(a.get("content_intro", "")) < 500]

    print(f"\n🎯 ASR 补提: {len(need)}/{len(bloggers)} 条\n")

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
