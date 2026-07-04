#!/usr/bin/env python3
"""MiMo ASR API 批量提取——使用小米 MiMo 替代本地 medium 模型"""
import sys, os, json, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from asr_extract import (
    download_asr, _kill_playwright, _clean_text,
    _SEEN_AUDIO_URLS, get_bilibili_content, get_audio_url
)

_kill_playwright()
_SEEN_AUDIO_URLS.clear()

with open("data.json", "r", encoding="utf-8-sig") as f:
    d = json.load(f)

videos = [a for a in d["articles"] if a.get("source") == "blogger"
          and ("douyin.com" in (a.get("url") or "") or "bilibili.com" in (a.get("url") or ""))]

print(f"MiMo ASR: {len(videos)} 条视频\n", flush=True)

def save():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

updated = 0
failed = 0

for i, v in enumerate(videos):
    url = v.get("url", "")
    name = v.get("blogger_name", "")
    aweme_id = v.get("aweme_id", "")
    platform = "B站" if "bilibili.com" in url else "抖音"

    print(f"[{i+1}/{len(videos)}] {name} ({platform})", flush=True)

    try:
        if "bilibili.com" in url:
            text = get_bilibili_content(url)
            if text and len(text) > 30:
                v["content_intro"] = _clean_text(text[:2000])
                updated += 1; save()
                print(f"  B站 {len(v['content_intro'])}字", flush=True)
            else:
                failed += 1
            continue

        vurl = get_audio_url(url, expected_aweme_id=aweme_id)
        if not vurl:
            if v.get("content_intro") and len(v["content_intro"]) > 100:
                print(f"  保留已有文案({len(v['content_intro'])}字)", flush=True)
            else:
                print(f"  未截获视频", flush=True)
                failed += 1
            continue

        print(f"  MiMo ASR...", flush=True)
        t0 = time.time()
        text, _ = download_asr(vurl, video_tag=aweme_id or str(i))
        elapsed = time.time() - t0

        if text and len(text) > 30:
            v["content_intro"] = _clean_text(text[:2000])
            updated += 1; save()
            print(f"  {elapsed:.0f}s, {len(v['content_intro'])}字", flush=True)
        else:
            failed += 1

    except Exception as e:
        print(f"  {e}", flush=True)
        failed += 1

    time.sleep(1); print()

_kill_playwright()

r = subprocess.run([sys.executable, "gen_js_data.py"], capture_output=True, text=True)
print(r.stdout.strip(), flush=True)
print(f"\nMiMo ASR: {updated}/{len(videos)} 成功, {failed} 失败", flush=True)
