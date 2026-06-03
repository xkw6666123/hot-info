#!/usr/bin/env python3
"""批量 ASR：对所有博主视频提取原文案，直接更新 data.json"""
import sys, os, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from asr_extract import (
    get_audio_url, download_asr, _kill_playwright, _clean_text,
    _SEEN_AUDIO_URLS, get_bilibili_content
)

_kill_playwright()
_SEEN_AUDIO_URLS.clear()

with open("data.json", "r", encoding="utf-8-sig") as f:
    d = json.load(f)

videos = [a for a in d["articles"] if a.get("source") == "blogger" 
          and ("douyin.com" in (a.get("url") or "") or "bilibili.com" in (a.get("url") or ""))]

print(f"\n🎬 批量 ASR: {len(videos)} 条视频\n")

def save():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

updated = 0
failed = 0

for i, v in enumerate(videos):
    url = v.get("url", "")
    name = v.get("blogger_name", "")
    title = (v.get("title") or "")[:40]
    aweme_id = v.get("aweme_id", "")
    platform = "B站" if "bilibili.com" in url else "抖音"
    
    print(f"[{i+1}/{len(videos)}] {name} ({platform}) | {title[:30]}")
    
    try:
        # B站：用字幕/ASR API
        if "bilibili.com" in url:
            text = get_bilibili_content(url)
            if text and len(text) > 30:
                v["content_intro"] = _clean_text(text[:2000])
                updated += 1
                save()
                print(f"  ✅ B站文案 {len(v['content_intro'])}字 (已保存)")
            else:
                print(f"  ⚠️ B站内容提取失败")
                failed += 1
            continue
        
        # 抖音：截获视频URL → 下载 → ASR
        print(f"  📡 截获视频流...")
        vurl = get_audio_url(url, expected_aweme_id=aweme_id)
        if not vurl:
            print(f"  ⚠️ 未截获视频，跳过")
            failed += 1
            continue
        
        print(f"  🎙️ ASR 识别中 (120s)...")
        t0 = time.time()
        text, uh = download_asr(vurl, aweme_id or str(i), max_sec=120)
        elapsed = time.time() - t0
        
        if text and len(text) > 30:
            v["content_intro"] = _clean_text(text[:2000])
            updated += 1
            save()
            print(f"  ✅ {elapsed:.0f}s, {len(v['content_intro'])}字 (已保存)")
        else:
            print(f"  ⚠️ ASR 无有效内容")
            failed += 1
    
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        failed += 1
        import traceback
        traceback.print_exc()
    
    # 每完成一条休息一下，避免被反爬
    time.sleep(2)
    print()

_kill_playwright()

# 重新生成 index.html
print("📄 重新生成 index.html...")
r = subprocess.run([sys.executable, "gen_js_data.py"], capture_output=True, text=True)
print(r.stdout.strip() if r.returncode == 0 else f"⚠️ {r.stderr[:200]}")

print(f"\n✅ 批量 ASR 完成: 成功 {updated}/{len(videos)}, 失败 {failed}")
