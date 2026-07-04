#!/usr/bin/env python3
"""ASR 一步到位"""
import sys, os, json, asyncio, subprocess, urllib.request, yaml
sys.stdout.reconfigure(line_buffering=True)

SCRIPT = r'C:\Users\Kevin\WorkBuddy\2026-05-08-task-5\hot-info'
sys.path.insert(0, SCRIPT)
from asr_extract import mimo_asr, _clean_text

DOUYIN = r'C:\Users\Kevin\WorkBuddy\2026-05-08-task-5\douyin-api'
sys.path.insert(0, DOUYIN)
os.chdir(DOUYIN)
from crawlers.douyin.web.web_crawler import DouyinWebCrawler

TEMP = os.path.join(SCRIPT, 'asr_temp')
os.makedirs(TEMP, exist_ok=True)

# Load Cookie for downloads  
with open(os.path.join(DOUYIN, 'crawlers', 'douyin', 'web', 'config.yaml'), 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
COOKIE = cfg['TokenManager']['douyin']['headers']['Cookie']

print("Reading data...")
with open(os.path.join(SCRIPT, 'data.json'), 'r', encoding='utf-8-sig') as f:
    d = json.load(f)

need = [a for a in d['articles'] if a.get('source') == 'blogger'
        and 'douyin.com' in (a.get('url') or '')
        and len(a.get('content_intro', '')) < 80]

print(f"Videos needing ASR: {len(need)}")
if not need:
    print("All done!")
    exit(0)

async def process(crawler, a, idx, total):
    aweme = a.get('aweme_id', '')
    print(f"\n[{idx}/{total}] {a['blogger_name']} aweme={aweme}", flush=True)
    
    resp = await crawler.fetch_one_video(aweme)
    detail = resp.get('aweme_detail', resp) if isinstance(resp, dict) else {}
    v = detail.get('video', {})
    
    urls = []
    dl = v.get('download_addr', {})
    if dl.get('url_list'):
        urls = dl['url_list']
    if not urls:
        for br in v.get('bit_rate', []):
            if br.get('play_addr', {}).get('url_list'):
                urls = br['play_addr']['url_list']; break
    
    if not urls:
        print("  FAIL: no URL"); return
    
    vurl = urls[0]
    mp3_path = os.path.join(TEMP, f'{aweme}.mp3')
    
    # 用 Python 带 Cookie 直接下载
    print("  Downloading...", flush=True)
    try:
        headers = {
            'Referer': 'https://www.douyin.com/',
            'Cookie': COOKIE,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(vurl, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) < 10000:
            print("  FAIL: download too small"); return
        tmp_mp4 = mp3_path + '.mp4'
        with open(tmp_mp4, 'wb') as f:
            f.write(data)
        sz_mb = len(data) / 1024 / 1024
        print(f"  Downloaded {sz_mb:.1f}MB, extracting audio...", flush=True)
    except Exception as e:
        print(f"  Download error: {e}"); return
    
    r = subprocess.run([
        'ffmpeg', '-y', '-i', tmp_mp4,
        '-t', '90', '-vn', '-ac', '1', '-ar', '16000',
        '-b:a', '32k', '-acodec', 'libmp3lame', mp3_path
    ], capture_output=True, timeout=30)
    os.remove(tmp_mp4)
    
    if r.returncode != 0:
        err = (r.stderr or b'').decode(errors='replace')[:200]
        print(f"  ffmpeg fail: {err}"); return
    
    sz = os.path.getsize(mp3_path) // 1024
    print(f"  Audio {sz}KB, ASR...", flush=True)
    
    try:
        # mimo_asr 接受文件路径
        text = mimo_asr(mp3_path)
        os.remove(mp3_path)
        if text:
            a['content_intro'] = _clean_text(text[:2000])
            with open(os.path.join(SCRIPT, 'data.json'), 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            print(f"  OK: {len(a['content_intro'])} chars", flush=True)
        else:
            print("  FAIL: empty result")
    except Exception as e:
        print(f"  ERROR: {e}")
        if os.path.exists(mp3_path): os.remove(mp3_path)

async def main():
    c = DouyinWebCrawler()
    for i, a in enumerate(need):
        await process(c, a, i+1, len(need))
    print(f"\nDONE! {len(need)} processed")

asyncio.run(main())
