#!/usr/bin/env python3
"""
扩展博主内容学习系统
1. 使用F2获取博主更多历史视频
2. 使用ASR提取完整文案
3. 更新学习数据
"""
import asyncio
import json
import os
import sys
import subprocess
import base64
import urllib.request
import time

# 配置
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
STYLE_FILE = os.path.join(os.path.dirname(__file__), "blogger_style_learned.json")
ASR_FILE = os.path.join(os.path.dirname(__file__), "asr_content.json")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "asr_temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# MiMo ASR API
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"

# 博主配置
BLOGGER_SEC_UIDS = {
    '网吧信息差': 'MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv',
    '阿七大型纪录片': 'MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf',
    '陈先生': 'MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF',
    '人类观察菌': 'MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN',
}


def get_f2_cookies():
    """获取抖音Cookie"""
    try:
        import browser_cookie3
        cj = browser_cookie3.chrome(domain_name='douyin.com')
        cookie_str = '; '.join(f'{c.name}={c.value}' for c in cj if 'douyin' in c.domain)
        return cookie_str
    except Exception as e:
        print(f"    ⚠️ Cookie读取失败: {e}")
        return ""


def mimo_asr(audio_path: str, language: str = "zh") -> str:
    """小米 MiMo ASR API"""
    if not MIMO_API_KEY:
        raise RuntimeError("MIMO_API_KEY 未设置")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    if len(audio_bytes) < 1000:
        return ""

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    mime = "audio/wav" if audio_path.endswith(".wav") else "audio/mpeg"

    payload = json.dumps({
        "model": "mimo-v2.5-asr",
        "messages": [{
            "role": "user",
            "content": [{
                "type": "input_audio",
                "input_audio": {"data": f"data:{mime};base64,{audio_b64}"}
            }]
        }],
        "asr_options": {"language": language},
        "max_tokens": 5000,
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{MIMO_BASE_URL}/chat/completions",
                data=payload, headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = ""
            if result.get("choices") and result["choices"][0].get("message"):
                text = result["choices"][0]["message"].get("content", "")
            return text.strip()
        except Exception as e:
            if attempt < 2:
                print(f"    MiMo 重试 {attempt+2}/3: {e}")
                time.sleep(3)
            else:
                print(f"    MiMo 失败: {e}")
                return ""


async def fetch_blogger_videos(name, sec_uid, cookie_str, count=10):
    """获取博主更多历史视频"""
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

    videos = []
    try:
        async for data in DouyinHandler(kwargs).fetch_user_post_videos(sec_uid, 0, 0, count, count):
            raw = data._to_raw()
            vlist = data._to_list()
            aweme_list = raw.get('aweme_list', [])
            for i, v in enumerate(aweme_list):
                lt = vlist[i] if i < len(vlist) else {}
                desc = (v.get('desc', '') or '').strip()
                ct = lt.get('create_time', '') if lt else ''
                aweme_id = str(v.get('aweme_id', ''))
                stats = v.get('statistics', {}) or {}
                digg = stats.get('digg_count', 0) or 0
                comment = stats.get('comment_count', 0) or 0

                videos.append({
                    'title': desc[:80],
                    'desc': desc,
                    'date': ct[:10] if ct else '',
                    'time': ct[11:16].replace('-', ':') if ct else '',
                    'aweme_id': aweme_id,
                    'url': f'https://www.douyin.com/video/{aweme_id}',
                    'likes': digg,
                    'comments': comment,
                    'blogger_name': name,
                })
    except Exception as e:
        print(f"  ❌ F2获取失败: {e}")

    return videos


def download_audio(url, output_path):
    """下载视频音频"""
    ffmpeg = "ffmpeg"
    cmd = [
        ffmpeg, "-y",
        "-headers", "Referer: https://www.douyin.com/\r\n",
        "-i", url, "-ac", "1", "-ar", "16000", "-t", "180", output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
    except:
        pass
    return False


async def process_video(video, cookie_str):
    """处理单个视频：获取下载URL → 下载音频 → ASR"""
    # 使用 Playwright 拦截方式获取视频URL（与 local_asr.py 相同的方式）
    DT_PATH = r"D:\AI\2026-06-06-23-33-48\douyin-transcribe"
    if DT_PATH not in sys.path:
        sys.path.insert(0, DT_PATH)

    aweme_id = video.get('aweme_id', '')
    url = video.get('url', '')
    if not aweme_id or not url:
        return ""

    # 使用 Playwright 拦截获取视频URL
    dl_url = None
    try:
        import server
        video_obj = await server._get_douyin_video_object(url)
        if isinstance(video_obj, dict):
            dl_url = server._pick_url_for_transcription(video_obj)
    except Exception as e:
        print(f"    Playwright拦截失败: {e}")

    if not dl_url:
        return ""

    # 下载音频
    wav_path = os.path.join(TEMP_DIR, f"asr_{aweme_id}.wav")
    if not download_audio(dl_url, wav_path):
        return ""

    # ASR
    text = mimo_asr(wav_path)

    # 清理
    try:
        os.remove(wav_path)
    except:
        pass

    if len(text) < 50:
        return ""

    return text[:5000]


async def main():
    if not MIMO_API_KEY:
        print("❌ 请设置 MIMO_API_KEY 环境变量")
        return

    cookie_str = get_f2_cookies()
    if not cookie_str:
        print("❌ 无法获取抖音Cookie")
        return

    # 读取现有数据
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    # 读取ASR备份
    asr_backup = {}
    if os.path.exists(ASR_FILE):
        with open(ASR_FILE, "r", encoding="utf-8") as f:
            asr_backup = json.load(f)

    # 获取每位博主更多视频
    all_new_videos = []
    for name, sec_uid in BLOGGER_SEC_UIDS.items():
        print(f"\n📹 获取 {name} 的历史视频...")
        videos = await fetch_blogger_videos(name, sec_uid, cookie_str, count=20)
        print(f"  获取到 {len(videos)} 条视频")

        # 过滤掉已有的视频
        existing_ids = set(b.get('aweme_id', '') for b in data.get('articles', [])
                         if b.get('source') == 'blogger' and b.get('blogger_name') == name)
        new_videos = [v for v in videos if v.get('aweme_id') not in existing_ids]
        print(f"  新视频: {len(new_videos)} 条")

        # 对新视频运行ASR
        for i, v in enumerate(new_videos[:5]):  # 每个博主最多5条新视频
            print(f"  [{i+1}/{min(len(new_videos), 5)}] {v.get('title', '')[:30]}...")
            text = await process_video(v, cookie_str)
            if text:
                v['content_intro'] = text
                all_new_videos.append(v)

                # 更新ASR备份
                asr_backup[v.get('aweme_id', '')] = {
                    'content_intro': text,
                    'blogger_name': name,
                    'title': v.get('title', ''),
                    'url': v.get('url', ''),
                    'aweme_id': v.get('aweme_id', ''),
                }
                print(f"    ✅ {len(text)}字")
            else:
                print(f"    ⚠️ ASR失败")

    # 保存ASR备份
    with open(ASR_FILE, "w", encoding="utf-8") as f:
        json.dump(asr_backup, f, ensure_ascii=False, indent=2)

    # 更新data.json
    if all_new_videos:
        # 添加新视频到data.json
        import hashlib
        def make_id(prefix, seed):
            return int(hashlib.md5(f'{prefix}_{seed}'.encode()).hexdigest()[:8], 16) % 10**9

        for v in all_new_videos:
            data['articles'].append({
                'id': make_id('f2', f'{v["blogger_name"]}_{v["aweme_id"]}') % 10**9,
                'title': v['title'],
                'summary': v['desc'][:200],
                'source': 'blogger',
                'blogger_name': v['blogger_name'],
                'date': v['date'],
                'time': v['time'],
                'tags': ['博主', '爆款', '拆解'],
                'url': v['url'],
                'likes': v['likes'],
                'comments': v['comments'],
                'aweme_id': v['aweme_id'],
                'content_intro': v.get('content_intro', ''),
            })

        with open(DATA_FILE, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 添加了 {len(all_new_videos)} 条新视频")

    # 重新学习风格
    print("\n=== 重新学习博主风格 ===")
    from learn_blogger_style import learn_all_styles
    learn_all_styles()

    print("\n✅ 完成！")


if __name__ == "__main__":
    asyncio.run(main())
