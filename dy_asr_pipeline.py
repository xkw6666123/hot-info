#!/usr/bin/env python3
"""本地抖音ASR流水线：playwright拦截音频URL → 立即下载 → 本地MiMo ASR
一次开浏览器处理全部视频，避免重复开关触发限流
"""
import subprocess, json, os, sys, time, base64, urllib.request

PCLI = r"C:\Users\Kevin\.workbuddy\binaries\node\versions\22.12.0\node.exe"
PCLI_SCRIPT = r"C:\Users\Kevin\.workbuddy\binaries\node\versions\22.12.0\playwright-cli"
MIMO_KEY = "tp-c03hkz73ublqqhz4q4ya5k75dwjh8igvzyf25h126nlhmack"
OUT_DIR = os.path.join(os.path.dirname(__file__), "asr_temp")
os.makedirs(OUT_DIR, exist_ok=True)

def pw(cmd, timeout=30):
    """Run playwright-cli command, return stdout"""
    r = subprocess.run([PCLI, PCLI_SCRIPT] + cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

def kill_all():
    try: subprocess.run([PCLI, PCLI_SCRIPT, "kill-all"], capture_output=True, timeout=5)
    except: pass

def get_audio_for_video(video_url, aweme_id):
    """Open video page, extract audio URL, download audio, run ASR"""
    out_audio = os.path.join(OUT_DIR, f"{aweme_id}.mp3")
    if os.path.exists(out_audio) and os.path.getsize(out_audio) > 1000:
        print(f"  [缓存] 已有音频 {os.path.getsize(out_audio)} bytes")
        return out_audio
    
    # Open the page
    print(f"  打开页面...", end="", flush=True)
    pw(["open", video_url])
    time.sleep(12)
    
    # Extract audio URL from performance entries
    print(f"提取音频URL...", end="", flush=True)
    audio_urls = pw(["eval", """
    (function(){
        var r=[];
        performance.getEntries().forEach(function(e){
            if(e.name.indexOf("douyinvod")>-1 && (e.name.indexOf("audio")>-1 || e.name.indexOf("media-audio")>-1))
                r.push(e.name);
        });
        if(r.length===0){
            // fallback: search all resource names
            performance.getEntries().forEach(function(e){
                if(e.name.indexOf("douyinvod")>-1 && e.name.indexOf(".mp4")===-1)
                    r.push(e.name);
            });
        }
        return JSON.stringify(r);
    })()
    """])
    
    try:
        urls = json.loads(audio_urls)
    except:
        urls = []
    
    if not urls:
        print(f" 未找到音频URL")
        return None
    
    audio_url = urls[0]
    print(f" 下载中...", end="", flush=True)
    
    # Download with ffmpeg while page still open
    subprocess.run([
        "ffmpeg", "-y", "-t", "90", "-i", audio_url,
        "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
        out_audio
    ], capture_output=True, timeout=60)
    
    if os.path.exists(out_audio) and os.path.getsize(out_audio) > 1000:
        print(f" {os.path.getsize(out_audio)} bytes")
        return out_audio
    else:
        print(f" 下载失败")
        return None

def run_asr(audio_path):
    """Run MiMo ASR on audio file"""
    if not os.path.exists(audio_path): return ""
    with open(audio_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    req = urllib.request.Request(
        'https://token-plan-cn.xiaomimimo.com/v1/audio/transcriptions',
        data=json.dumps({'model':'mimo','file':audio_b64,'language':'zh'}).encode(),
        headers={'Authorization': f'Bearer {MIMO_KEY}','Content-Type':'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=120)
    return json.loads(resp.read()).get('text', '')

def main():
    # Load data
    with open('data.json', 'r', encoding='utf-8-sig') as f:
        d = json.load(f)
    
    todo = [a for a in d['articles'] 
            if a.get('source')=='blogger' 
            and 'douyin.com' in (a.get('url') or '') 
            and len(a.get('content_intro','')) < 100]
    
    print(f"需处理: {len(todo)} 条")
    
    kill_all()
    time.sleep(2)
    
    updated = 0
    for i, a in enumerate(todo):
        url = a['url']
        import re; m = re.search(r'/video/(\d+)', url)
        aweme_id = m.group(1) if m else ''
        
        print(f"\n[{i+1}/{len(todo)}] {a['blogger_name']} {aweme_id[:8]}")
        
        audio = get_audio_for_video(url, aweme_id)
        if audio:
            print(f"  ASR中...", end="", flush=True)
            text = run_asr(audio)
            if text and len(text) > 30:
                a['content_intro'] = text
                updated += 1
                print(f" ✅ {len(text)}字")
                with open('data.json', 'w', encoding='utf-8') as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
            else:
                print(f" ⚠️ ASR空")
        
        # Small delay between videos
        time.sleep(3)
    
    kill_all()
    
    # Verify
    for a in d['articles']:
        if a.get('source')=='blogger':
            ci = a.get('content_intro','')
            s = "✅" if len(ci)>100 else "⏳"
            print(f"  [{a['blogger_name']}] {len(ci)}字 {s}")
    
    print(f"\n本次更新: {updated} 条")

if __name__ == "__main__":
    main()
