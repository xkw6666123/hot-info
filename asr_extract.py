#!/usr/bin/env python3
"""免费 ASR：Playwright 拦截音频 → ffmpeg下载 → Whisper → 摘要"""
import json, os, subprocess, time, re, sys, shutil, hashlib, whisper

# 自动检测 ffmpeg 路径
FFMPEG = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe") or "ffmpeg"
PCLI = "playwright-cli"
WORK = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(WORK, "asr_temp")
os.makedirs(TMP, exist_ok=True)

# Whisper 模型全局单例（只加载一次，优先 medium，内存不够用 small）
_whisper_model = None
def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            _whisper_model = whisper.load_model("medium")
            print("  🎤 Whisper medium 加载成功")
        except Exception:
            _whisper_model = whisper.load_model("small")
            print("  🎤 Whisper medium 内存不足，回退 small")
    return _whisper_model

def _kill_playwright():
    """完全关闭 Playwright 浏览器，确保状态干净"""
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} kill-all"],
                   capture_output=True, timeout=10)
    time.sleep(1)

def get_audio_url(video_url, expected_aweme_id=""):
    """Playwright 打开视频页，从网络请求中截获音频 URL
    返回 (audio_url, response_html_len) 或 (None, 0)
    expected_aweme_id: 用于验证截获的音频是否属于当前视频
    """
    _kill_playwright()
    
    # 打开页面，用 longer wait + retry if page fails to load
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} open \"{video_url}\""],
                capture_output=True, timeout=30, text=True, encoding="utf-8", errors="replace"
            )
            break
        except subprocess.TimeoutExpired:
            if attempt < 2:
                _kill_playwright()
                time.sleep(3)
    
    time.sleep(7)  # 给页面足够时间加载和发起音频请求
    
    # 获取网络请求列表
    r = subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} requests"],
                       capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
    
    requests_output = r.stdout
    
    # 找到 audio URL (media-audio-und-mp4a)，验证是否包含当前视频的 aweme_id
    import urllib.parse
    
    best_audio = None
    
    for line in requests_output.split("\n"):
        if "media-audio-und-mp4a" in line and "douyinvod.com" in line:
            parts = line.split("=>")
            for part in parts:
                if "douyinvod.com" in part:
                    url_raw = part.strip().split(" ")[-1].strip("[]")
                    url = urllib.parse.unquote(url_raw)
                    # 验证 audio URL 是否与期望视频匹配
                    if expected_aweme_id and expected_aweme_id in url:
                        _kill_playwright()
                        return url
                    # 记录第一个找到的 audio URL 作为备选
                    if not best_audio:
                        best_audio = url
    
    # 如果有备选 audio URL（不匹配 aweme_id 但可能是正确的），返回它
    if best_audio:
        _kill_playwright()
        return best_audio
    
    # 如果没找到音频，找 video URL（MP4，后续用 ffmpeg 提取音频）
    for line in requests_output.split("\n"):
        if "media-video-avc1" in line and "douyinvod.com" in line:
            parts = line.split("=>")
            for part in parts:
                if "douyinvod.com" in part:
                    url_raw = part.strip().split(" ")[-1].strip("[]")
                    url = urllib.parse.unquote(url_raw)
                    _kill_playwright()
                    return url
    
    _kill_playwright()
    return None

# 全局去重：记录已处理的音频 URL，防止跨视频复用
_SEEN_AUDIO_URLS = set()

def download_asr(audio_url, video_tag=""):
    """下载音频 → ASR → 摘要
    video_tag: 用于区分不同视频的临时文件标识
    返回 (summary, audio_url_hash) 或 ("", "")
    """
    global _SEEN_AUDIO_URLS
    
    # 音频 URL 去重：同一段音频不重复处理
    url_hash = hashlib.md5(audio_url.encode()).hexdigest()[:12]
    if url_hash in _SEEN_AUDIO_URLS:
        print(f"    ⚠️ 音频 URL 重复，跳过")
        return "", ""
    _SEEN_AUDIO_URLS.add(url_hash)
    
    tag = video_tag or url_hash
    mp4 = os.path.join(TMP, f"_pw_{tag}.mp4")
    wav = os.path.join(TMP, f"_pw_{tag}.wav")
    
    # ffmpeg 下载
    subprocess.run([FFMPEG, "-y", "-i", audio_url, "-c", "copy", "-t", "180", mp4],
                   capture_output=True, timeout=60)
    if not os.path.exists(mp4) or os.path.getsize(mp4) < 1000:
        return "", ""
    
    # 转 WAV
    subprocess.run([FFMPEG, "-y", "-i", mp4, "-ac", "1", "-ar", "16000", "-t", "180", wav],
                   capture_output=True, timeout=30)
    
    if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
        for f in [mp4, wav]:
            try: os.remove(f)
            except: pass
        return "", ""
    
    # Whisper
    model = get_whisper()
    r = model.transcribe(wav, language="zh", fp16=False, verbose=False)
    text = r["text"].strip()
    
    # 清理临时文件
    for f in [mp4, wav]:
        try: os.remove(f)
        except: pass
    
    # 质量检查：无明显内容的转录丢弃
    if len(text) < 10:
        return "", url_hash
    # 检查是否全是噪声（随机字符比例过高）
    alpha_ratio = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff') / max(len(text), 1)
    if alpha_ratio < 0.3:
        print(f"    ⚠️ 转录质量过低（中文占比 {alpha_ratio:.1%}），丢弃")
        return "", url_hash
    
    # 摘要
    events = re.split(r'(?=第[一二三四五六七八九十\d]+[件事个]|首先|另外|还有|接下来|最后|OK|下一件事)', text)
    if len(events) > 1:
        return "\n".join(f"  · {e.strip()[:80]}" for e in events[:6] if len(e.strip()) > 10), url_hash
    return text[:500], url_hash

def main():
    global _SEEN_AUDIO_URLS
    _SEEN_AUDIO_URLS = set()  # 每次运行重置
    
    _kill_playwright()
    
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d["articles"] if a.get("source") == "blogger" and "douyin.com" in (a.get("url") or "")]
    
    print(f"\n🎉 免费 ASR: {len(bloggers)} 条视频\n")
    
    # 先收集所有已有的 content_intro，用于跨视频去重
    existing_intros = set()
    for v in bloggers:
        ci = v.get("content_intro", "")
        if ci and len(ci) > 20:
            existing_intros.add(ci)
    
    updated = 0
    skipped_dup = 0
    for i, v in enumerate(bloggers):
        url = v.get("url", "")
        name = v.get("blogger_name", "")
        title = v.get("title", "")[:30]
        aweme_id = v.get("aweme_id", "")
        
        print(f"[{i+1}/{len(bloggers)}] {name} | {title}")
        
        try:
            audio_url = get_audio_url(url, expected_aweme_id=aweme_id)
            if not audio_url:
                print(f"  ⚠️ 未截获音频")
                continue
            
            summary, url_hash = download_asr(audio_url, video_tag=aweme_id or str(i))
            if not summary:
                print(f"  ⚠️ ASR 失败或无有效内容")
                continue
            
            # 跨视频去重：如果转录内容与已有内容高度相似，跳过
            if summary in existing_intros:
                print(f"  ⚠️ 内容与已有视频重复，跳过")
                skipped_dup += 1
                continue
            
            # 简单相似度检查：如果摘要的前50字符与已有内容的某条匹配
            short = summary[:50]
            is_dup = False
            for ei in existing_intros:
                if short in ei or ei[:50] in summary:
                    print(f"  ⚠️ 内容与已有视频高度相似，跳过")
                    skipped_dup += 1
                    is_dup = True
                    break
            if is_dup:
                continue
            
            v["content_intro"] = summary
            existing_intros.add(summary)
            updated += 1
            print(f"  ✅ {len(summary)}字")
        except Exception as e:
            print(f"  ❌ {e}")
        print()
    
    if updated:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        r = subprocess.run([sys.executable, "gen_js_data.py"], cwd=WORK, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ⚠️ gen_js_data 失败: {r.stderr[:200]}")
    
    _kill_playwright()
    print(f"\n✅ 更新 {updated}/{len(bloggers)}，跳过重复 {skipped_dup}")

if __name__ == "__main__":
    main()
