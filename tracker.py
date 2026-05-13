#!/usr/bin/env python3
"""
独立博主追踪器：通过 iesdouyin 公开 API 获取博主最新视频。
不依赖 TikHub/Playwright/cookies（使用无需登录的 API）。
每个博主保留最新 3 条，新视频替换旧视频。
"""
import urllib.request, json, hashlib, datetime, os, sys, time

WORK = os.path.dirname(os.path.abspath(__file__))

# 博主配置：name + sec_uid（从 iesdouyin API 获取，无需 cookies）
BLOGGERS = [
    {"name": "网吧信息差", "unique_id": ""},       # TODO: 填入 unique_id
    {"name": "阿七大型纪录片", "unique_id": ""},
    {"name": "陈先生", "unique_id": "chenxiansheng274", "sec_uid": "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF"},
    {"name": "信息黑板报", "unique_id": ""},
    {"name": "人类观察菌", "unique_id": ""},
]

def make_id(prefix, raw):
    return int(hashlib.md5(f"{prefix}_{raw}".encode()).hexdigest()[:8], 16) % 10**9

def api_get(url, referer="https://www.douyin.com/"):
    """调用 iesdouyin API"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": referer,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    ❌ API 失败: {e}")
        return None

def get_sec_uid(unique_id):
    """通过 unique_id 获取 sec_uid"""
    url = f"https://www.iesdouyin.com/web/api/v2/user/info/?unique_id={unique_id}"
    data = api_get(url, f"https://www.douyin.com/user/{unique_id}")
    if data:
        user = data.get("user_info", data.get("user", {}))
        return user.get("sec_uid", "")
    return ""

def fetch_blogger_videos(blogger):
    """抓取博主最新 3 条视频"""
    name = blogger["name"]
    sec_uid = blogger.get("sec_uid", "")
    unique_id = blogger.get("unique_id", "")

    if not sec_uid and unique_id:
        sec_uid = get_sec_uid(unique_id)
        if sec_uid:
            blogger["sec_uid"] = sec_uid
            print(f"    🔑 sec_uid: {sec_uid[:20]}...")
        else:
            print(f"    ❌ 无法获取 sec_uid（需要 unique_id）")
            return []

    if not sec_uid:
        print(f"    ⚠️ 缺少 sec_uid 和 unique_id，跳过")
        return []

    # 获取最新 3 条视频
    url = f"https://www.iesdouyin.com/web/api/v2/aweme/post/?sec_uid={sec_uid}&count=3&max_cursor=0"
    ref = f"https://www.douyin.com/user/{unique_id}" if unique_id else "https://www.douyin.com/"
    data = api_get(url, ref)

    if not data:
        return []

    awemes = data.get("aweme_list", [])
    if not awemes:
        print(f"    ⚠️ API 返回 0 条视频（可能需要登录 cookies）")
        return []

    videos = []
    for v in awemes[:3]:
        aweme_id = v.get("aweme_id", "")
        desc = v.get("desc", "").strip()
        stats = v.get("statistics", {})
        video = {
            "id": make_id("blogger", f"{name}_{aweme_id}") % 10**9,
            "title": desc[:200] if desc else f"{name}视频",
            "summary": desc[:500],
            "source": "blogger",
            "blogger_name": name,
            "date": datetime.datetime.fromtimestamp(v.get("create_time", 0)).strftime("%Y-%m-%d") if v.get("create_time") else datetime.date.today().isoformat(),
            "time": datetime.datetime.fromtimestamp(v.get("create_time", 0)).strftime("%H:%M") if v.get("create_time") else "00:00",
            "tags": [],
            "url": f"https://www.douyin.com/video/{aweme_id}",
            "likes": stats.get("digg_count", 0),
            "comments": stats.get("comment_count", 0),
            "aweme_id": aweme_id,
            "platform": "douyin",
            "content_intro": "",  # 留给 ASR 填充
        }
        videos.append(video)
        print(f"    ✅ {aweme_id} | ❤{video['likes']} | {video['date']} | {desc[:40]}")

    return videos

def update_data_json():
    """更新 data.json，保持每个博主最新 3 条"""
    # 读取现有数据
    with open(os.path.join(WORK, "data.json"), "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    all_articles = data.get("articles", [])
    non_blogger = [a for a in all_articles if a.get("source") != "blogger"]

    # 按博主分组现有数据
    existing_by_blogger = {}
    for a in all_articles:
        if a.get("source") == "blogger":
            name = a.get("blogger_name", "")
            if name not in existing_by_blogger:
                existing_by_blogger[name] = []
            existing_by_blogger[name].append(a)

    today = datetime.date.today().isoformat()
    total_new = 0

    for blogger in BLOGGERS:
        name = blogger["name"]
        print(f"\n📡 {name}")
        new_videos = fetch_blogger_videos(blogger)

        if not new_videos:
            print(f"    ⚠️ 未获取到新视频，保留旧数据")
            continue

        # 合并新旧视频，按 aweme_id 去重
        existing = existing_by_blogger.get(name, [])
        existing_ids = {v.get("aweme_id", "") for v in existing}
        merged = existing[:]

        for nv in new_videos:
            if nv["aweme_id"] not in existing_ids:
                merged.append(nv)
                total_new += 1

        # 按日期排序（新 → 旧），保留最新 3 条
        merged.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)
        kept = merged[:3]
        removed = merged[3:]

        if removed:
            print(f"    🧹 移除 {len(removed)} 条旧视频")
        print(f"    📊 {name}: 共 {len(merged)} 条，保留 {len(kept)} 条")

        # 更新 existing_by_blogger
        existing_by_blogger[name] = kept

    # 重建文章列表
    new_articles = non_blogger[:]
    for items in existing_by_blogger.values():
        new_articles.extend(items)

    data["articles"] = new_articles
    data["updated_at"] = datetime.datetime.now().isoformat()

    with open(os.path.join(WORK, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 更新完成: {len(new_articles)} 条 | 新增: {total_new}")

if __name__ == "__main__":
    update_data_json()
