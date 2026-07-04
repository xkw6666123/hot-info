#!/usr/bin/env python3
"""批量 ASR v2: 小米 MiMo ASR API + 增强纠错"""
import sys, os, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 强制刷新输出
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

from asr_extract import (
    get_audio_url, download_asr, _kill_playwright, _clean_text,
    _SEEN_AUDIO_URLS, get_bilibili_content, mimo_asr
)

_kill_playwright()
_SEEN_AUDIO_URLS.clear()

print("🚀 小米 MiMo ASR API 就绪\n")

with open("data.json", "r", encoding="utf-8-sig") as f:
    d = json.load(f)

videos = [a for a in d["articles"] if a.get("source") == "blogger" 
          and ("douyin.com" in (a.get("url") or "") or "bilibili.com" in (a.get("url") or ""))]

print(f"🎬 批量 ASR v2 (beam search): {len(videos)} 条视频\n")

def save():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

# 直接使用 asr_extract.download_asr（现已是 MiMo API）

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
        text, uh = download_asr(vurl, aweme_id or str(i), max_sec=150)
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
