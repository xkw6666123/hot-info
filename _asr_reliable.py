#!/usr/bin/env python3
"""
可靠 ASR 流水线: douyin-api 获取下载链接 → ffmpeg下载+提取音频 → MiMo ASR
"""
import sys, os, json, time, asyncio, subprocess, tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOUYIN_API_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'douyin-api')

# 先导入 asr_extract (在 hot-info 目录)
sys.path.insert(0, SCRIPT_DIR)
from asr_extract import mimo_asr, _clean_text

# 再切换到 douyin-api 目录导入爬虫
sys.path.insert(0, DOUYIN_API_DIR)
os.chdir(DOUYIN_API_DIR)
from crawlers.douyin.web.web_crawler import DouyinWebCrawler

FFMPEG = "ffmpeg"
TEMP_DIR = os.path.join(SCRIPT_DIR, "asr_temp")
os.makedirs(TEMP_DIR, exist_ok=True)

async def get_video_url(crawler, aweme_id):
    """获取视频下载 URL"""
    resp = await crawler.fetch_one_video(aweme_id)
    aweme = resp.get('aweme_detail', resp) if isinstance(resp, dict) else {}
    video = aweme.get('video', {})
    
    # 尝试不同来源获取 URL
    download = video.get('download_addr', {})
    url_list = download.get('url_list', [])
    
    if not url_list:
        play = video.get('play_addr', {})
        url_list = play.get('url_list', [])
    
    if not url_list:
        # 尝试 bit_rate
        for br in video.get('bit_rate', []):
            pa = br.get('play_addr', {})
            if pa.get('url_list'):
                url_list = pa['url_list']
                break
    
    return url_list[0] if url_list else None

def download_and_asr(video_url, output_prefix, max_sec=150):
    """下载视频 → 提取音频 → MiMo ASR"""
    audio_path = os.path.join(TEMP_DIR, f"{output_prefix}.m4a")
    
    # ffmpeg 下载并提取音频
    cmd = [
        FFMPEG, "-y",
        "-headers", "Referer: https://www.douyin.com/\r\n",
        "-i", video_url,
        "-t", str(max_sec),
        "-vn", "-acodec", "aac",
        audio_path
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, timeout=60, check=True)
        
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
            return None
        
        # MiMo ASR
        with open(audio_path, 'rb') as af:
            text = mimo_asr(af.read())
        
        # 清理
        os.remove(audio_path)
        return _clean_text(text[:2000]) if text else None
    
    except Exception as e:
        print(f"    ⚠️ ffmpeg/ASR 失败: {e}")
        return None

async def main():
    # 读取数据
    with open(os.path.join(SCRIPT_DIR, "data.json"), "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    # 找需要 ASR 的视频（content_intro 为空或很短）
    need_asr = []
    for a in d["articles"]:
        if a.get("source") != "blogger":
            continue
        if "douyin.com" not in (a.get("url") or ""):
            continue
        ci = a.get("content_intro", "")
        if len(ci) < 80:
            need_asr.append(a)
    
    if not need_asr:
        print("✅ 所有视频已有完整文案！")
        return
    
    print(f"🎯 需要 ASR: {len(need_asr)} 条")
    print()
    
    crawler = DouyinWebCrawler()
    updated = 0
    failed = 0
    
    for i, a in enumerate(need_asr):
        aweme_id = a.get("aweme_id", "")
        name = a["blogger_name"]
        title = a.get("title", "")[:40]
        url = a.get("url", "")
        
        print(f"[{i+1}/{len(need_asr)}] {name}")
        print(f"  {title}")
        
        try:
            video_url = await get_video_url(crawler, aweme_id)
            if not video_url:
                print(f"  ⚠️ 未获取到下载链接\n")
                failed += 1
                continue
            
            print(f"  📥 下载中...")
            t0 = time.time()
            text = download_and_asr(video_url, aweme_id)
            elapsed = time.time() - t0
            
            if text and len(text) > 30:
                a["content_intro"] = text
                updated += 1
                # 每处理完一条就保存
                with open(os.path.join(SCRIPT_DIR, "data.json"), "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
                print(f"  ✅ {elapsed:.0f}s, {len(text)}字\n")
            else:
                print(f"  ⚠️ ASR 结果太短\n")
                failed += 1
        
        except Exception as e:
            print(f"  ❌ {e}\n")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"✅ 完成: {updated}条更新, {failed}条失败")

if __name__ == "__main__":
    asyncio.run(main())
