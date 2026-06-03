#!/usr/bin/env python3
"""批量 ASR v2: 优化Whisper参数(temperature=0 + beam_size=5) + 增强纠错"""
import sys, os, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 强制刷新输出
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

from asr_extract import (
    get_audio_url, download_asr, _kill_playwright, _clean_text,
    _SEEN_AUDIO_URLS, get_bilibili_content, get_whisper
)
import whisper as _whisper

_kill_playwright()
_SEEN_AUDIO_URLS.clear()

# 预热 Whisper 模型（加载一次，所有视频共用）
print("🔥 预热 Whisper 模型...")
model = get_whisper()
print("✅ 模型就绪\n")

with open("data.json", "r", encoding="utf-8-sig") as f:
    d = json.load(f)

videos = [a for a in d["articles"] if a.get("source") == "blogger" 
          and ("douyin.com" in (a.get("url") or "") or "bilibili.com" in (a.get("url") or ""))]

print(f"🎬 批量 ASR v2 (beam search): {len(videos)} 条视频\n")

def save():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def asr_whisper(wav_path):
    """直接调用 Whisper 模型（避免重复加载）"""
    r = model.transcribe(wav_path, language="zh", fp16=False, verbose=False,
                         temperature=0.0, beam_size=5, best_of=5,
                         condition_on_previous_text=False)
    return r["text"].strip()

# Monkey-patch download_asr to use pre-warmed model
import asr_extract
_orig_download = asr_extract.download_asr

def _patched_download(audio_url, video_tag="", max_sec=120):
    """Monkey-patched version that uses pre-warmed model"""
    global _SEEN_AUDIO_URLS
    import hashlib
    url_hash = hashlib.md5(audio_url.encode()).hexdigest()[:12]
    if url_hash in _SEEN_AUDIO_URLS:
        return "", ""
    _SEEN_AUDIO_URLS.add(url_hash)
    
    tag = video_tag or url_hash
    mp4 = os.path.join(asr_extract.TMP, f"_pw_{tag}.mp4")
    wav = os.path.join(asr_extract.TMP, f"_pw_{tag}.wav")
    
    ffmpeg_cmd = [asr_extract.FFMPEG, "-y", "-i", audio_url, "-c", "copy", "-t", str(max_sec), mp4]
    if "douyinvod.com" in audio_url or "douyin.com" in audio_url:
        ffmpeg_cmd = [asr_extract.FFMPEG, "-y", "-headers", "Referer: https://www.douyin.com/\r\n", 
                      "-i", audio_url, "-c", "copy", "-t", str(max_sec), mp4]
    subprocess.run(ffmpeg_cmd, capture_output=True, timeout=60)
    if not os.path.exists(mp4) or os.path.getsize(mp4) < 1000:
        return "", ""
    
    subprocess.run([asr_extract.FFMPEG, "-y", "-i", mp4, "-ac", "1", "-ar", "16000", "-t", str(max_sec), wav],
                   capture_output=True, timeout=30)
    if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
        for f in [mp4, wav]:
            try: os.remove(f)
            except: pass
        return "", ""
    
    text = asr_whisper(wav)
    text = _clean_text(text)
    for f in [mp4, wav]:
        try: os.remove(f)
        except: pass
    
    if len(text) < 10:
        return "", url_hash
    alpha_ratio = sum(1 for c in text if '\u4e00' <= c <= '\u9fff') / max(len(text), 1)
    if alpha_ratio < 0.3:
        return "", url_hash
    return text[:2000], url_hash

asr_extract.download_asr = _patched_download

updated = 0
failed = 0

for i, v in enumerate(videos):
    url = v.get("url", "")
    name = v.get("blogger_name", "")
    title = (v.get("title") or "")[:40]
    aweme_id = v.get("aweme_id", "")
    platform = "B站" if "bilibili.com" in url else "抖音"
    
    print(f"[{i+1}/{len(videos)}] {name} ({platform})", flush=True)
    
    try:
        if "bilibili.com" in url:
            text = get_bilibili_content(url)
            if text and len(text) > 30:
                v["content_intro"] = _clean_text(text[:2000])
                updated += 1; save()
                print(f"  ✅ B站 {len(v['content_intro'])}字", flush=True)
            else:
                print(f"  ⚠️ 跳过", flush=True); failed += 1
            continue
        
        vurl = get_audio_url(url, expected_aweme_id=aweme_id)
        if not vurl:
            print(f"  ⚠️ 未截获视频", flush=True); failed += 1
            continue
        
        t0 = time.time()
        text, uh = asr_extract.download_asr(vurl, aweme_id or str(i), max_sec=150)
        elapsed = time.time() - t0
        
        if text and len(text) > 30:
            v["content_intro"] = _clean_text(text[:2000])
            updated += 1; save()
            print(f"  ✅ {elapsed:.0f}s, {len(v['content_intro'])}字", flush=True)
        else:
            print(f"  ⚠️ ASR失败", flush=True); failed += 1
    
    except Exception as e:
        print(f"  ❌ {e}", flush=True); failed += 1
    
    time.sleep(2); print()

_kill_playwright()

# Generate index.html
print("📄 生成 index.html...", flush=True)
r = subprocess.run([sys.executable, "gen_js_data.py"], capture_output=True, text=True)
print(r.stdout.strip(), flush=True)

print(f"\n✅ 完成: {updated}/{len(videos)} 成功, {failed} 失败", flush=True)
