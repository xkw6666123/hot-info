#!/usr/bin/env python3
"""免费的抖音博主视频抓取 (Playwright Python API)
原理: 打开博主主页 → 拦截 aweme/post API 响应 → 提取视频列表
需要: pip install playwright && playwright install chromium
"""
import json, os, sys, time, hashlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

TODAY = datetime.now().strftime("%Y-%m-%d")
NOW = datetime.now().strftime("%H:%M")

# 博主列表：name → sec_uid (从抖音视频页提取)
BLOGGERS = {
    "网吧信息差": "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv",
    "阿七大型纪录片": "",
    "陈先生": "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF",
    "信息黑板报": "",
    "人类观察菌": "",
}


def make_id(prefix, seed):
    return int(hashlib.md5(f"{prefix}_{seed}".encode()).hexdigest()[:8], 16) % 10 ** 9


def get_blogger_sec_uid(playwright, name):
    """通过视频页面的API获取博主的sec_uid"""
    # 先尝试用已有的视频URL
    import json as _json
    try:
        with open("data.json", "r", encoding="utf-8-sig") as f:
            data = _json.load(f)
    except Exception:
        return None

    # 找到该博主的任意一个视频URL
    video_url = None
    for a in data.get("articles", []):
        if a.get("blogger_name") == name and "douyin.com/video/" in a.get("url", ""):
            video_url = a["url"]
            break

    if not video_url:
        return None

    # 打开视频页
    page = playwright.pages[0] if playwright.pages else None
    if not page:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

    captured = {"sec_uid": None}

    def handle_response(response):
        if "aweme/v1/web/aweme/detail" in response.url and response.status == 200:
            try:
                body = response.json()
                author = body.get("aweme_detail", {}).get("author", {})
                if author.get("sec_uid"):
                    captured["sec_uid"] = author["sec_uid"]
            except Exception:
                pass

    page.on("response", handle_response)
    page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    page.remove_listener("response", handle_response)
    return captured["sec_uid"]


def scrape_blogger_videos(playwright, name, sec_uid, count=5):
    """打开博主主页，拦截视频列表API"""
    page = playwright.pages[0] if playwright.pages else playwright.chromium.launch(headless=True).new_page()

    captured = {"videos": []}

    def handle_response(response):
        if "aweme/v1/web/aweme/post" in response.url and response.status == 200:
            try:
                body = response.json()
                for v in body.get("aweme_list", [])[:count]:
                    stats = v.get("statistics", {}) or {}
                    captured["videos"].append(
                        {
                            "aweme_id": str(v.get("aweme_id", "")),
                            "desc": (v.get("desc", "") or "")[:200],
                            "create_time": v.get("create_time", 0),
                            "likes": stats.get("digg_count", stats.get("diggCount", 0)),
                            "comments": stats.get("comment_count", stats.get("commentCount", 0)),
                        }
                    )
            except Exception:
                pass

    page.on("response", handle_response)
    profile_url = f"https://www.douyin.com/user/{sec_uid}"
    page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(8)
    page.remove_listener("response", handle_response)
    return captured["videos"]


def scrape_bloggers_free():
    """免费的博主视频抓取，输出为generate_hot.py兼容格式"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️ playwright 未安装，pip install playwright && playwright install chromium")
        return []

    articles = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for name, sec_uid in BLOGGERS.items():
            print(f"  📹 {name}...")

            # 解析sec_uid
            if not sec_uid:
                sec_uid = get_blogger_sec_uid(p, name)
            if not sec_uid:
                print(f"    ⚠️ 未找到sec_uid，跳过")
                continue

            try:
                page = browser.new_page()
                videos = scrape_blogger_videos(p, name, sec_uid)
                page.close()

                if not videos:
                    print(f"    ⚠️ 未截获视频数据")
                    continue

                for v in videos[:5]:
                    aweme_id = v.get("aweme_id", "")
                    desc = v.get("desc", "")
                    create_time = v.get("create_time", 0)
                    date = (
                        datetime.fromtimestamp(create_time).strftime("%Y-%m-%d")
                        if create_time
                        else TODAY
                    )
                    t = (
                        datetime.fromtimestamp(create_time).strftime("%H:%M")
                        if create_time
                        else NOW
                    )

                    articles.append(
                        {
                            "id": make_id("pw_blogger", f"{name}_{aweme_id}") % 10 ** 9,
                            "title": desc[:80] if desc else f"{name} 最新视频",
                            "summary": desc[:200] if desc else "",
                            "source": "blogger",
                            "blogger_name": name,
                            "date": date,
                            "time": t,
                            "tags": ["博主", "爆款", "拆解"],
                            "url": f"https://www.douyin.com/video/{aweme_id}",
                            "likes": v.get("likes", 0),
                            "comments": v.get("comments", 0),
                            "aweme_id": aweme_id,
                        }
                    )

                print(f"    ✅ 找到 {len(videos)} 条视频")
            except Exception as e:
                print(f"    ❌ {e}")

        browser.close()

    return articles


if __name__ == "__main__":
    articles = scrape_bloggers_free()
    print(f"\n📊 总计: {len(articles)} 条视频")
    if articles:
        from pprint import pprint

        pprint(articles[:3])
