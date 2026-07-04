#!/usr/bin/env python3
"""批量ASR v4：F2获取视频信息 → urllib下载音频 → MiMo ASR → 更新 data.json"""
import json, os, sys, time, base64, subprocess, urllib.request, asyncio, re

MIMO_KEY = "tp-c03hkz73ublqqhz4q4ya5k75dwjh8igvzyf25h126nlhmack"
MIMO_URL = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
TMP = os.path.join(os.path.dirname(__file__), "asr_temp")
os.makedirs(TMP, exist_ok=True)
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
FFMPEG = "ffmpeg"

def get_f2_cookies():
    try:
        import browser_cookie3
        cj = browser_cookie3.chrome(domain_name='douyin.com')
        cookie_str = '; '.join('{}={}'.format(c.name, c.value) for c in cj if 'douyin' in c.domain)
        return cookie_str
    except Exception as e:
        print(f"    ⚠️ Cookie读取失败: {e}")
        return ""

def get_video_download_url(aweme_id, cookie_str):
    """Use F2 to get video info and extract download URL"""
    from f2.apps.douyin.handler import DouyinHandler
    
    kwargs = {
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.douyin.com/',
        },
        'proxies': {'http://': None, 'https://': None},
        'timeout': 10,
        'cookie': cookie_str,
    }
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
    except:
        pass
    
    async def _fetch():
        handler = DouyinHandler(kwargs)
        try:
            async for data in handler.fetch_user_post_videos("", 0, 0, 1, 1):
                # This won't work - we need a different approach
                pass
        except:
            pass
        
        # Try fetch_one_video
        try:
            result = await handler.fetch_one_video(aweme_id)
            async for data in result:
                raw = data._to_raw()
                if 'aweme_detail' in raw:
                    ad = raw['aweme_detail']
                    video = ad.get('video', {})
                    # Try to get download URL from bit_rate
                    br_list = video.get('bit_rate', [])
                    if br_list:
                        # Prefer lower quality for faster download
                        br_list.sort(key=lambda x: x.get('bit_rate', 999999))
                        for br in br_list:
                            pa = br.get('play_addr', {})
                            url_list = pa.get('url_list', [])
                            if url_list:
                                return url_list[0]
                    # Fallback: play_addr
                    pa = video.get('play_addr', {})
                    url_list = pa.get('url_list', [])
                    if url_list:
                        return url_list[0]
        except Exception as e:
            print(f"    F2单视频获取失败: {e}")
        
        return None
    
    try:
        return asyncio.run(_fetch())
    except Exception as e:
        print(f"    F2异步失败: {e}")
        return None

def download_audio_direct(url, aweme_id, cookie_str):
    """Download audio from douyin CDN URL using urllib + ffmpeg"""
    out_wav = os.path.join(TMP, f"{aweme_id}.wav")
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
        return out_wav
    
    # For douyin, the video URL might need specific headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Referer': 'https://www.douyin.com/',
        'Cookie': cookie_str,
    }
    
    # Use ffmpeg to download and extract audio directly
    out_mp3 = os.path.join(TMP, f"{aweme_id}.mp3")
    cmd = [
        FFMPEG, "-y",
        "-headers", f"User-Agent: {headers['User-Agent']}\r\nReferer: {headers['Referer']}\r\nCookie: {cookie_str}",
        "-i", url,
        "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
        "-t", "120",  # max 2 min
        out_mp3
    ]
    
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000:
            # Convert to wav for MiMo
            wav_cmd = [FFMPEG, "-y", "-i", out_mp3, "-ar", "16000", "-ac", "1", out_wav]
            subprocess.run(wav_cmd, capture_output=True, timeout=30)
            if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
                os.remove(out_mp3)
                return out_wav
        return out_mp3 if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000 else None
    except Exception as e:
        print(f"    ffmpeg下载失败: {e}")
        return None

def mimo_asr(audio_path):
    """MiMo v2.5 ASR using base64"""
    if not os.path.exists(audio_path):
        return ""
    with open(audio_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    
    if len(audio_b64) < 1000:
        return ""
    
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
                time.sleep(3)
    return ""

def build_intro_from_title(a):
    """为没有完整ASR的视频，用标题+互动数据构建较丰富的文案"""
    title = a.get('title', '').strip()
    likes = a.get('likes', 0) or 0
    comments = a.get('comments', 0) or 0
    parts = [f"📹 {title}"]
    if likes:
        parts.append(f"👍 {likes//10000}万赞" if likes >= 10000 else f"👍 {likes}赞")
    if comments:
        parts.append(f"💬 {comments}评论")
    return "\n".join(parts)

def main():
    cookie_str = get_f2_cookies()
    if not cookie_str:
        print("Cookie获取失败，无法继续")
        return
    
    with open(DATA_FILE, 'r', encoding='utf-8-sig') as f:
        d = json.load(f)
    
    todo = []
    for a in d['articles']:
        if a.get('source') == 'blogger':
            ci = a.get('content_intro', '')
            url = a.get('url', '')
            if 'douyin.com' in url and len(ci) < 100:
                m = re.search(r'/video/(\d+)', url)
                aweme_id = m.group(1) if m else ''
                todo.append((a, url, aweme_id, len(ci)))
    
    print(f"需要ASR: {len(todo)} 条")
    
    if not todo:
        # Still build better intros for those with only title+stats
        for a in d['articles']:
            if a.get('source') == 'blogger' and len(a.get('content_intro','')) < 50:
                a['content_intro'] = build_intro_from_title(a)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print("全部已有文案！")
        return
    
    updated = 0
    for i, (a, url, aweme_id, old_len) in enumerate(todo):
        bn = a.get('blogger_name', '?')
        title = a.get('title', '')[:30]
        print(f"\n[{i+1}/{len(todo)}] {bn} | {aweme_id[:8]}")
        
        # Get video download URL via F2
        video_url = get_video_download_url(aweme_id, cookie_str)
        if not video_url:
            print(f"    ❌ 无法获取视频URL，用标题填充")
            a['content_intro'] = build_intro_from_title(a)
            continue
        
        print(f"    下载中...", end="", flush=True)
        audio = download_audio_direct(video_url, aweme_id, cookie_str)
        if not audio:
            print(f" 失败，用标题填充")
            a['content_intro'] = build_intro_from_title(a)
            continue
        
        print(f" ASR中...", end="", flush=True)
        text = mimo_asr(audio)
        if text and len(text) > 30:
            a['content_intro'] = text
            updated += 1
            print(f" ✅ {len(text)}字")
        else:
            print(f" ⚠️ ({len(text)}字)，用标题填充")
            a['content_intro'] = build_intro_from_title(a)
        
        if audio and os.path.exists(audio):
            os.remove(audio)
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        
        time.sleep(3)
    
    print(f"\n━━━━━━━━━━━━━━━━━━━━")
    print(f"ASR完成: {updated}/{len(todo)} 条")
    
    # Final cleanup: ensure all blogger entries have >= 50 char intro
    for a in d['articles']:
        if a.get('source') == 'blogger' and len(a.get('content_intro', '')) < 50:
            a['content_intro'] = build_intro_from_title(a)
    
    print("\n最终状态:")
    for a in d['articles']:
        if a.get('source') == 'blogger':
            ci = a.get('content_intro', '')
            bn = a.get('blogger_name', '?')
            s = "✅" if len(ci) > 100 else ("⚠️" if len(ci) >= 50 else "⏳")
            print(f"  [{bn}] {len(ci)}字 {s}")
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
