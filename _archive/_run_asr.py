import os, sys, asyncio, json, subprocess, time, re, shutil, base64, urllib.request, urllib.error
import warnings
warnings.filterwarnings("ignore")

# 强制无缓冲输出
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

os.environ['MIMO_API_KEY'] = 'tp-c03hkz73ublqqhz4q4ya5k75dwjh8igvzyf25h126nlhmack'
sys.path.insert(0, r'D:\AI\2026-06-06-23-33-48\douyin-transcribe')

print("Loading douyin-transcribe server...")
import server as srv
print("OK")

PROJECT = r'D:\AI\2026-06-06-23-33-48\hot-info'
FFMPEG = shutil.which('ffmpeg') or 'ffmpeg'
TEMP = os.path.join(PROJECT, 'asr_temp')
os.makedirs(TEMP, exist_ok=True)

print("Reading data.json...")
with open(os.path.join(PROJECT, 'data.json'), 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

bloggers = [a for a in data['articles'] if a.get('source') == 'blogger']
need = [a for a in bloggers if len(a.get('content_intro', '')) < 100]
print(f'Need ASR: {len(need)}/{len(bloggers)}')

if not need:
    print("All done!")
    sys.exit(0)

MIMO_API_KEY = os.environ.get('MIMO_API_KEY', '')
MIMO_BASE_URL = 'https://token-plan-cn.xiaomimimo.com/v1'

def mimo_asr(audio_path):
    with open(audio_path, 'rb') as f:
        audio_bytes = f.read()
    if len(audio_bytes) < 1000:
        return ''
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
    mime = 'audio/wav' if audio_path.endswith('.wav') else 'audio/mpeg'
    payload = json.dumps({
        'model': 'mimo-v2.5-asr',
        'messages': [{'role': 'user', 'content': [{'type': 'input_audio', 'input_audio': {'data': f'data:{mime};base64,{audio_b64}'}}]}],
        'asr_options': {'language': 'zh'},
        'max_tokens': 3000,
    }).encode('utf-8')
    headers = {'Authorization': f'Bearer {MIMO_API_KEY}', 'Content-Type': 'application/json'}
    for attempt in range(3):
        try:
            req = urllib.request.Request(f'{MIMO_BASE_URL}/chat/completions', data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return text.strip()
        except Exception as e:
            if attempt < 2:
                print(f'    Retry {attempt+2}: {e}')
                time.sleep(3)
            else:
                print(f'    FAIL: {e}')
                return ''

async def process_one(aweme_id, url, tag):
    print(f'  [1/3] Intercept {tag}...')
    video = await srv._get_douyin_video_object(url)
    dl = srv._pick_url_for_transcription(video)
    if not dl:
        print('    No URL')
        return ''
    print(f'    URL: {dl[:70]}...')
    
    print(f'  [2/3] Download...')
    wav = os.path.join(TEMP, f'asr_{tag}.wav')
    cmd = [FFMPEG, '-y',
        '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        '-headers', 'Referer: https://www.douyin.com/',
        '-i', dl, '-ac', '1', '-ar', '16000', '-t', '180', wav]
    subprocess.run(cmd, capture_output=True, timeout=180)
    if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
        subprocess.run([FFMPEG, '-y', '-user_agent', 'Mozilla/5.0', '-i', dl, '-ac', '1', '-ar', '16000', '-t', '180', wav], capture_output=True, timeout=180)
    sz = os.path.getsize(wav) if os.path.exists(wav) else 0
    print(f'    Size: {sz//1024}KB')
    
    if sz < 10:
        return ''
    
    print(f'  [3/3] MiMo ASR...')
    text = mimo_asr(wav)
    try: os.remove(wav)
    except: pass
    print(f'    Result: {len(text)} chars')
    return text[:2000] if len(text) > 20 else ''

async def main():
    updated = 0
    for i, v in enumerate(need):
        name = v.get('blogger_name', '')
        aweme_id = v.get('aweme_id', '')
        url = v.get('url', '')
        if 'douyin.com' not in url:
            continue
        print(f'\n[{i+1}/{len(need)}] {name}')
        try:
            text = await process_one(aweme_id, url, aweme_id)
            if text and len(text) > 50:
                v['content_intro'] = text
                updated += 1
                print(f'    OK {len(text)}字: {text[:60]}...')
        except Exception as e:
            import traceback
            print(f'    ERR: {e}')
            traceback.print_exc()
    
    if updated:
        data['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        with open(os.path.join(PROJECT, 'data.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        subprocess.run([sys.executable, 'gen_js_data.py'], cwd=PROJECT)
    print(f'\nDone: {updated} updated')

asyncio.run(main())
