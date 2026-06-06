#!/usr/bin/env python3
"""精简 ASR: 只处理缺失文案的视频，去重，跳过已有"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

from asr_extract import get_audio_url, download_asr, _kill_playwright, _clean_text, get_bilibili_content

_kill_playwright()
time.sleep(1)

with open("data.json", "r", encoding="utf-8-sig") as f:
    d = json.load(f)

# 筛选：需要 ASR 的视频（content_intro < 100字），去重 aweme_id
seen_aweme = set()
videos = []
for a in d["articles"]:
    if a.get("source") != "blogger":
        continue
    ci = a.get("content_intro", "")
    if len(ci) >= 100:
        continue
    aid = a.get("aweme_id", a.get("id", ""))
    if aid in seen_aweme:
        continue
    seen_aweme.add(aid)
    videos.append(a)

print(f"🎯 需要 ASR: {len(videos)} 条视频\n")

if not videos:
    print("✅ 全部视频已有完整文案！")
    sys.exit(0)

def save():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

updated = 0; failed = 0

for i, v in enumerate(videos):
    url = v.get("url", "")
    name = v.get("blogger_name", "")
    title = v.get("title", "")[:40]
    aweme_id = v.get("aweme_id", "")
    platform = "B站" if "bilibili.com" in url else "抖音"
    
    print(f"[{i+1}/{len(videos)}] {name} ({platform})", flush=True)
    print(f"  {title}", flush=True)
    
    try:
        if "bilibili.com" in url:
            text = get_bilibili_content(url)
            if text and len(text) > 30:
                v["content_intro"] = _clean_text(text[:2000])
                updated += 1; save()
                print(f"  ✅ B站 {len(v['content_intro'])}字\n", flush=True)
            else:
                print(f"  ⚠️ 跳过\n", flush=True); failed += 1
            continue
        
        # 抖音：使用较短超时
        vurl = get_audio_url(url, expected_aweme_id=aweme_id)
        if not vurl:
            print(f"  ⚠️ 未截获音频URL (可能需登录或验证码)\n", flush=True)
            failed += 1
            continue
        
        t0 = time.time()
        text, uh = download_asr(vurl, aweme_id or str(i), max_sec=120)
        elapsed = time.time() - t0
        
        if text and len(text) > 30:
            v["content_intro"] = _clean_text(text[:2000])
            updated += 1; save()
            print(f"  ✅ {elapsed:.0f}s, {len(v['content_intro'])}字\n", flush=True)
        else:
            print(f"  ⚠️ ASR失败\n", flush=True); failed += 1
    
    except Exception as e:
        print(f"  ❌ {e}\n", flush=True); failed += 1

_kill_playwright()

print(f"\n{'='*50}")
print(f"✅ 完成: {updated}条更新, {failed}条失败")
print(f"📁 data.json 已保存")
