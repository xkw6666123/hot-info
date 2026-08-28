#!/usr/bin/env python3
"""用 SenseVoiceSmall 重新转写所有博主视频（替换旧的不准文案）。
复用 whisper_asr_local.py 的音频下载 + 转写函数（已切换到 SenseVoice）。
"""
import json, os, sys

WORK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORK)
os.chdir(WORK)
sys.stdout.reconfigure(encoding='utf-8')

import whisper_asr_local as w

DATA_FILE = os.path.join(WORK, "data.json")


def main():
    data = json.load(open(DATA_FILE, encoding="utf-8-sig"))
    bloggers = [a for a in data.get("articles", []) if a.get("source") == "blogger"]
    print(f"🎯 重新转写 {len(bloggers)} 条博主视频（SenseVoiceSmall）\n")

    done = 0
    for i, a in enumerate(bloggers):
        name = a.get("blogger_name", "?")
        title = (a.get("title") or "")[:25]
        url = a.get("url", "")
        tag = a.get("aweme_id") or str(a.get("id", i))
        print(f"[{i+1}/{len(bloggers)}] {name} | {title}")
        try:
            if "douyin.com" in url:
                wav = w.get_douyin_audio(url, tag)
            elif "bilibili.com" in url:
                wav = w.get_bilibili_audio(url, tag)
            else:
                print("    ⚠️ 未知平台，跳过")
                continue
            if not wav:
                print("    ❌ 音频下载失败")
                continue
            text = w.transcribe(wav)
            try:
                os.remove(wav)
            except OSError:
                pass
            if len(text) < 20:
                print(f"    ⚠️ 转写过短({len(text)}字)，跳过")
                continue
            a["content_intro"] = text
            done += 1
            print(f"    ✅ {len(text)}字: {text[:40]}...")
            # 每条即时保存，防中断丢失
            json.dump(data, open(DATA_FILE + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(DATA_FILE + ".tmp", DATA_FILE)
        except Exception as e:
            print(f"    ❌ {type(e).__name__}: {str(e)[:100]}")

    print(f"\n✅ 完成 {done}/{len(bloggers)} 条")


if __name__ == "__main__":
    main()
