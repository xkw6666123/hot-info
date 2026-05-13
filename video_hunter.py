#!/usr/bin/env python3
"""
video_hunter.py — 视频素材猎人
从博主视频文案提取事件关键词 → 抖音搜索原始素材 → 下载干净视频到本地
供剪映二次创作使用

用法:
  python video_hunter.py                     # 分析所有博主，搜索+下载
  python video_hunter.py --dry-run           # 只搜索预览，不下载
  python video_hunter.py --blogger "信息黑板报"  # 只分析指定博主
  python video_hunter.py --max-per-keyword 3 # 每词最多下载3条
"""
import json, os, sys, re, time, urllib.request, urllib.error, hashlib
from datetime import datetime

# ── 配置 ──
WORK = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(WORK, "data.json")
OUTPUT_ROOT = os.path.join(os.path.expanduser("~"), "Videos", "剪映素材")
TIKHUB_BASE = "https://api.tikhub.io"
TIKHUB_KEY = "srAlG/ROjGy6h0XKAoib+DTMbQKKX6Ns/SbJvkumTaW8jVOVPVyHSROeOw=="
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# 已追踪博主名（避免下载自己的素材）
TRACKED_NAMES = {"网吧信息差", "阿七大型纪录片", "信息黑板报", "人类观察菌", "沙漠一之雕", "陈先生"}

# ── 工具函数 ──
def tikhub_search(keyword, count=5):
    """搜索抖音视频（POST）"""
    url = f"{TIKHUB_BASE}/api/v1/douyin/search/fetch_video_search_v2"
    headers = {
        "Authorization": f"Bearer {TIKHUB_KEY}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json"
    }
    data = json.dumps({"keyword": keyword, "cursor": 0, "count": count}).encode()
    try:
        req = urllib.request.Request(url, headers=headers, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode())
        
        if raw.get("code") != 200:
            return []
        
        business_data = raw.get("data", {}).get("business_data", [])
        videos = []
        for item in business_data:
            if item.get("type") != 1:  # type=1 是普通视频
                continue
            info = item.get("data", {}).get("aweme_info", item.get("data", {}))
            if not isinstance(info, dict):
                continue
            
            video_urls = []
            video = info.get("video", {})
            # 优先无水印下载链接
            for addr_type in ["download_addr", "play_addr"]:
                addr = video.get(addr_type, {})
                url_list = addr.get("url_list", [])
                if url_list:
                    video_urls = url_list
                    break
            
            if not video_urls:
                continue
            
            author = info.get("author", {})
            videos.append({
                "aweme_id": info.get("aweme_id", ""),
                "desc": (info.get("desc") or "").strip(),
                "duration": info.get("duration", 0),
                "download_url": video_urls[0],
                "author_name": author.get("nickname", ""),
                "author_uid": author.get("uid", ""),
                "play_count": (info.get("statistics", {}) or {}).get("play_count", 0),
                "hashtag_count": (info.get("desc") or "").count("#"),
            })
        return videos
    except Exception as e:
        print(f"  ⚠️ 搜索 '{keyword}' 失败: {type(e).__name__}")
        return []


def extract_keywords(content_intro):
    """从 ASR 文案中提取搜索关键词
    策略：取每段事件的中段核心词（跳过开头引导语），生成短+中2个版本
    """
    keywords = []
    if not content_intro or len(content_intro) < 50:
        return keywords
    
    # 按事件行分割
    lines = re.split(r'[·\n]', content_intro.replace("\n", " "))
    
    for line in lines:
        line = line.strip()
        if len(line) < 12:
            continue
        
        # 去掉标点和引导语
        cleaned = re.sub(r'[，。！？、；：""''（）【】…—\s]', '', line)
        
        # 跳过开头无意义的引导词
        lead_patterns = [
            r'^首先', r'^接下来', r'^最后一个', r'^最后', r'^另外', r'^还有',
            r'^OK', r'^这个', r'^那个', r'^然后', r'^就是', r'^热点信息差',
            r'^今日热点', r'^逆天事件合集', r'^熱點信息差', r'^此前',
            r'^真的是', r'^确实', r'^说实话', r'^怎么说', r'^不过',
        ]
        for pat in lead_patterns:
            if re.match(pat, cleaned):
                cleaned = re.sub(pat, '', cleaned, count=1)
                break
        
        if len(cleaned) < 8:
            continue
        
        # 生成两个版本：
        # 短版：前 15-18 字（更有搜索命中率）
        short_kw = cleaned[:18] if len(cleaned) > 18 else cleaned
        if short_kw not in keywords and len(short_kw) >= 8:
            keywords.append(short_kw)
        
        # 长版：前 25-30 字（更精确匹配）
        if len(cleaned) > 22:
            long_kw = cleaned[:28]
            if long_kw not in keywords and long_kw != short_kw:
                keywords.append(long_kw)
    
    return keywords[:8]  # 每个视频最多 8 个搜索词


def filter_videos(videos, keyword):
    """过滤视频：去掉不合适的"""
    filtered = []
    for v in videos:
        # 跳过已追踪博主的视频
        if v["author_name"] in TRACKED_NAMES:
            continue
        
        # 时长过滤：10s ~ 10min
        duration_sec = v["duration"] / 1000
        if duration_sec < 10 or duration_sec > 600:
            continue
        
        # 话题标签太多 → 可能过度编辑
        if v["hashtag_count"] > 6:
            continue
        
        # 描述太短 → 可能无内容
        if len(v["desc"]) < 10:
            continue
        
        filtered.append(v)
    
    # 按播放量降序
    filtered.sort(key=lambda x: -x["play_count"])
    return filtered


def download_video(download_url, filepath, max_mb=100):
    """下载视频到本地，超过 max_mb 则跳过"""
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        print(f"    📁 已存在: {os.path.basename(filepath)}")
        return True
    
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.douyin.com/"
    }
    
    try:
        req = urllib.request.Request(download_url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            total_mb = total / (1024 * 1024)
            if total_mb > max_mb:
                print(f"    ⏭️ 跳过 ({total_mb:.0f}MB > {max_mb}MB)")
                return False
            data = resp.read()
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(data)
        
        size_mb = len(data) / (1024 * 1024)
        print(f"    ✅ {size_mb:.1f}MB")
        return True
    except Exception as e:
        print(f"    ❌ 下载失败: {type(e).__name__}: {str(e)[:50]}")
        return False


def sanitize_filename(text):
    """文件名安全化，保留核心关键词"""
    text = re.sub(r'[\\/:*?"<>|]', '', text)
    text = re.sub(r'\s+', '', text)
    return text[:30]  # 缩短文件名


# ── 主流程 ──
def main():
    dry_run = "--dry-run" in sys.argv
    target_blogger = None
    max_per_kw = 3
    
    for i, arg in enumerate(sys.argv):
        if arg == "--blogger" and i + 1 < len(sys.argv):
            target_blogger = sys.argv[i + 1]
        if arg == "--max-per-keyword" and i + 1 < len(sys.argv):
            max_per_kw = int(sys.argv[i + 1])
    
    # 1. 读取博主视频文案
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d.get("articles", [])
                if a.get("source") == "blogger"]
    
    if target_blogger:
        bloggers = [a for a in bloggers if a.get("blogger_name") == target_blogger]
        if not bloggers:
            print(f"未找到博主: {target_blogger}")
            return
    
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n🎯 视频素材猎人")
    print(f"   博主数: {len(bloggers)} | 模式: {'预览' if dry_run else '下载'} | 每词上限: {max_per_kw}")
    print(f"   输出目录: {OUTPUT_ROOT}\\{today}\\\n")
    
    total_found = 0
    total_downloaded = 0
    all_videos_seen = set()  # 去重
    
    for bi, blog in enumerate(bloggers):
        name = blog.get("blogger_name", "")
        ci = blog.get("content_intro", "")
        
        if len(ci) < 50:
            continue
        
        print(f"[{bi+1}/{len(bloggers)}] 📊 {name}")
        
        # 2. 提取关键词
        keywords = extract_keywords(ci)
        if not keywords:
            print(f"    ⚠️ 无有效关键词\n")
            continue
        
        print(f"    🔑 {len(keywords)} 个搜索词\n")
        
        for kw in keywords[:5]:  # 每个视频最多搜 5 个词
            print(f"    🔍 搜索: {kw}")
            
            # 3. 搜索
            videos = tikhub_search(kw, count=5)
            if not videos:
                print(f"      ⚠️ 无结果\n")
                continue
            
            # 4. 过滤
            candidates = filter_videos(videos, kw)
            if not candidates:
                print(f"      ⚠️ 无合适视频\n")
                continue
            
            print(f"      📋 找到 {len(candidates)} 个候选视频:")
            
            for vi, v in enumerate(candidates[:max_per_kw]):
                vid = v["aweme_id"]
                if vid in all_videos_seen:
                    continue
                all_videos_seen.add(vid)
                
                dur = v["duration"] / 1000
                desc_short = v["desc"][:40]
                print(f"        [{vi+1}] {desc_short} | {dur:.0f}s | {v['author_name']}")
                
                total_found += 1
                
                if dry_run:
                    continue
                
                # 5. 下载
                date_folder = os.path.join(OUTPUT_ROOT, today)
                safe_kw = sanitize_filename(kw[:30])
                filename = f"{today}_{safe_kw}_{vid}.mp4"
                filepath = os.path.join(date_folder, filename)
                
                if download_video(v["download_url"], filepath):
                    total_downloaded += 1
            
            print()
            time.sleep(1)  # 避免请求过快
    
    # 总结
    print("=" * 50)
    print(f"📊 汇总: 找到 {total_found} 个素材视频")
    if not dry_run:
        print(f"📥 下载: {total_downloaded} 个到 {OUTPUT_ROOT}\\{today}\\")
    else:
        print(f"💡 预览模式, 使用 python video_hunter.py 实际下载")
    print("=" * 50)


if __name__ == "__main__":
    main()
