#!/usr/bin/env python3
"""批量ASR v3：yt-dlp + Chrome cookies 下载音频 → MiMo ASR → 更新 data.json"""
import json, os, sys, time, base64, subprocess, urllib.request

MIMO_KEY = "tp-c03hkz73ublqqhz4q4ya5k75dwjh8igvzyf25h126nlhmack"
MIMO_URL = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
TMP = os.path.join(os.path.dirname(__file__), "asr_temp")
os.makedirs(TMP, exist_ok=True)
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
YTDLP = [sys.executable, "-m", "yt_dlp"]

def download_audio(url, aweme_id):
    """yt-dlp with Chrome cookies, extract audio only"""
    out = os.path.join(TMP, f"{aweme_id}.%(ext)s")
    out_wav = os.path.join(TMP, f"{aweme_id}.wav")
    
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
        print(f"    [缓存] {os.path.getsize(out_wav)} bytes")
        return out_wav
    
    # Check for mp3/m4a
    for ext in ['.wav', '.mp3', '.m4a']:
        p = os.path.join(TMP, f"{aweme_id}{ext}")
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            return p
    
    cmd = YTDLP + [
        "--cookies-from-browser", "chrome",
        "-f", "worstaudio",  # smallest audio to save time
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "32K",
        "-o", out,
        "--max-filesize", "10M",
        "--no-playlist",
        "--socket-timeout", "30",
        url
    ]
    
    print(f"    yt-dlp 下载中...", end="", flush=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        # Find downloaded file
        for ext in ['.wav', '.mp3', '.m4a']:
            p = os.path.join(TMP, f"{aweme_id}{ext}")
            if os.path.exists(p) and os.path.getsize(p) > 1000:
                print(f" {os.path.getsize(p)} bytes [{ext}]")
                return p
        print(f" 失败: {r.stderr[-200:] if r.stderr else 'no output'}")
        return None
    except subprocess.TimeoutExpired:
        print(" 超时")
        return None
    except Exception as e:
        print(f" 错误: {e}")
        return None

def mimo_asr(audio_path):
    """MiMo v2.5 ASR"""
    if not os.path.exists(audio_path):
        return ""
    with open(audio_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    
    if len(audio_b64) < 1000:
        return ""
    
    # Determine mime type
    ext = os.path.splitext(audio_path)[1].lower()
    mime_map = {'.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4'}
    mime = mime_map.get(ext, 'audio/mpeg')
    
    payload = json.dumps({
        'model': 'mimo-v2.5-asr',
        'messages': [{
            'role': 'user',
            'content': [{
                'type': 'input_audio',
                'input_audio': {
                    'data': f'data:{mime};base64,{audio_b64}'
                }
            }]
        }],
        'asr_options': {'language': 'zh'},
        'max_tokens': 3000
    }).encode('utf-8')
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                MIMO_URL,
                data=payload,
                headers={
                    'Authorization': f'Bearer {MIMO_KEY}',
                    'Content-Type': 'application/json'
                }
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            
            text = ''
            if result.get('choices') and result['choices'][0].get('message'):
                text = result['choices'][0]['message'].get('content', '')
            return text.strip()
        except Exception as e:
            if attempt < 2:
                print(f"    ASR重试 {attempt+2}/3: {e}")
                time.sleep(3)
    return ""

def main():
    with open(DATA_FILE, 'r', encoding='utf-8-sig') as f:
        d = json.load(f)
    
    # Find blogger videos that need ASR (content_intro < 100 chars and douyin source)
    todo = []
    for a in d['articles']:
        if a.get('source') == 'blogger':
            ci = a.get('content_intro', '')
            url = a.get('url', '')
            if 'douyin.com' in url and len(ci) < 100:
                import re
                m = re.search(r'/video/(\d+)', url)
                aweme_id = m.group(1) if m else ''
                todo.append((a, url, aweme_id, len(ci)))
    
    print(f"需要ASR: {len(todo)} 条")
    if not todo:
        print("全部已有完整文案！")
        return
    
    updated = 0
    for i, (a, url, aweme_id, old_len) in enumerate(todo):
        bn = a.get('blogger_name', '?')
        title = a.get('title', '')[:30]
        print(f"\n[{i+1}/{len(todo)}] {bn} | {aweme_id[:8]} | {title}")
        print(f"    当前文案: {old_len}字 → 需要ASR")
        
        audio = download_audio(url, aweme_id)
        if not audio:
            print(f"    ❌ 音频下载失败，跳过")
            continue
        
        print(f"    ASR中...", end="", flush=True)
        text = mimo_asr(audio)
        if text and len(text) > 30:
            a['content_intro'] = text
            updated += 1
            print(f" ✅ {len(text)}字")
            # Save immediately
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        else:
            print(f" ⚠️ ASR结果太短({len(text)}字)")
        
        # Clean up audio file to save space
        if audio and os.path.exists(audio):
            os.remove(audio)
        
        time.sleep(2)
    
    print(f"\n━━━━━━━━━━━━━━━━━━━━")
    print(f"ASR完成: 更新 {updated}/{len(todo)} 条")
    
    # Verify
    print("\n最终状态:")
    for a in d['articles']:
        if a.get('source') == 'blogger':
            ci = a.get('content_intro', '')
            bn = a.get('blogger_name', '?')
            s = "✅" if len(ci) > 100 else "⏳"
            print(f"  [{bn}] {len(ci)}字 {s}")
    
    # Save final
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
