#!/usr/bin/env python3
"""
最终方案: douyin API → music.play_url (直链 mp3) → MiMo ASR
无需 Playwright，无需 ffmpeg，直接下载 mp3
"""
import sys, os, json, asyncio, urllib.request, time

SCRIPT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT)
from asr_extract import mimo_asr, _clean_text

DOUYIN = os.path.join(os.path.dirname(SCRIPT), 'douyin-api')
sys.path.insert(0, DOUYIN)
os.chdir(DOUYIN)
from crawlers.douyin.web.web_crawler import DouyinWebCrawler
import yaml

# 加载 Cookie 用于下载
with open(os.path.join(DOUYIN, 'crawlers', 'douyin', 'web', 'config.yaml'), 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
COOKIE = cfg['TokenManager']['douyin']['headers']['Cookie']

TEMP = os.path.join(SCRIPT, 'asr_temp')
os.makedirs(TEMP, exist_ok=True)

async def get_music_url(crawler, aweme_id):
    """获取音乐 mp3 直链"""
    resp = await crawler.fetch_one_video(aweme_id)
    aweme = resp.get('aweme_detail', resp) if isinstance(resp, dict) else {}
    music = aweme.get('music', {})
    play_url = music.get('play_url', {})
    urls = play_url.get('url_list', [])
    return urls[0] if urls else None

def download_mp3(url, output_path):
    """下载 mp3"""
    headers = {
        'Referer': 'https://www.douyin.com/',
        'Cookie': COOKIE,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            with open(output_path, 'wb') as f:
                f.write(data)
            return len(data)
    except Exception as e:
        print(f"    download error: {e}")
        return 0

async def process_one(crawler, a, idx, total):
    aweme_id = a.get('aweme_id', '')
    name = a['blogger_name']
    print(f"\n[{idx}/{total}] {name} aweme={aweme_id}", flush=True)
    
    # 1. 获取音乐 mp3 URL
    music_url = await get_music_url(crawler, aweme_id)
    if not music_url:
        print("  FAIL: no music URL"); return
    print(f"  Music URL: {music_url[:80]}...", flush=True)
    
    # 2. 下载 mp3
    mp3_path = os.path.join(TEMP, f'{aweme_id}.mp3')
    size = download_mp3(music_url, mp3_path)
    if size < 5000:
        print(f"  FAIL: mp3 too small ({size} bytes)"); return
    if size > 8 * 1024 * 1024:  # 超过 8MB 跳过
        print(f"  SKIP: mp3 too large ({size//1024}KB > 8MB)"); return
    print(f"  MP3: {size//1024}KB", flush=True)
    
    # 3. MiMo ASR
    print("  ASR...", flush=True)
    try:
        text = mimo_asr(mp3_path)
        os.remove(mp3_path)
        if text and len(text) > 30:
            a['content_intro'] = _clean_text(text[:2000])
            with open(os.path.join(SCRIPT, 'data.json'), 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            print(f"  DONE: {len(a['content_intro'])} chars", flush=True)
        else:
            print(f"  FAIL: empty ASR ({len(text) if text else 0} chars)", flush=True)
    except Exception as e:
        print(f"  FAIL: {e}", flush=True)
        if os.path.exists(mp3_path): os.remove(mp3_path)

async def main():
    print("Reading data...")
    with open(os.path.join(SCRIPT, 'data.json'), 'r', encoding='utf-8-sig') as f:
        global d
        d = json.load(f)
    
    need = [a for a in d['articles'] if a.get('source') == 'blogger'
            and 'douyin.com' in (a.get('url') or '')
            and len(a.get('content_intro', '')) < 80]
    
    if not need:
        print("All done!"); return
    
    print(f"Videos needing ASR: {len(need)}")
    crawler = DouyinWebCrawler()
    
    for i, a in enumerate(need):
        t0 = time.time()
        await process_one(crawler, a, i+1, len(need))
        print(f"  ({time.time()-t0:.0f}s)", flush=True)
        # 避免 API 限流
        if i < len(need) - 1:
            time.sleep(5)
    
    print(f"\nDone! {len(need)} processed")

d = None
asyncio.run(main())
