#!/usr/bin/env python3
"""免费的抖音博主视频抓取 — 使用 Douyin_TikTok_Download_API 核心模块
直接调用 A_Bogus 签名 + API，无需启动Web服务
"""
import json, os, sys, asyncio, hashlib
from datetime import datetime

# 将此脚本所在目录加入 path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOUYIN_API_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "douyin-api")
sys.path.insert(0, DOUYIN_API_DIR)
os.chdir(DOUYIN_API_DIR)

from crawlers.douyin.web.web_crawler import DouyinWebCrawler

TODAY = datetime.now().strftime("%Y-%m-%d")
NOW = datetime.now().strftime("%H:%M")

BLOGGERS = {
    "网吧信息差": "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv",
    "阿七大型纪录片": "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf",
    "陈先生": "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF",
    "人类观察菌": "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN",
}


def make_id(prefix, seed):
    return int(hashlib.md5(f"{prefix}_{seed}".encode()).hexdigest()[:8], 16) % 10 ** 9


async def scrape_all():
    crawler = DouyinWebCrawler()
    articles = []

    for name, sec_uid in BLOGGERS.items():
        print(f"📹 {name}...")
        try:
            response = await crawler.fetch_user_post_videos(sec_uid, max_cursor=0, count=5)
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {e}")
            continue

        aweme_list = response.get("aweme_list", [])
        print(f"  {len(aweme_list)}条")
        for v in aweme_list[:5]:
            aweme_id = str(v.get("aweme_id", ""))
            desc = (v.get("desc", "") or "")[:200]
            stats = v.get("statistics", {}) or {}
            ct = v.get("create_time", 0)

            date, t = TODAY, NOW
            if ct:
                try:
                    dt = datetime.fromtimestamp(int(ct))
                    date = dt.strftime("%Y-%m-%d")
                    t = dt.strftime("%H:%M")
                except:
                    pass

            articles.append(
                {
                    "id": make_id("free", f"{name}_{aweme_id}") % 10 ** 9,
                    "title": desc[:80] if desc else f"{name} 最新视频",
                    "summary": desc,
                    "source": "blogger",
                    "blogger_name": name,
                    "date": date,
                    "time": t,
                    "tags": ["博主", "爆款", "拆解"],
                    "url": f"https://www.douyin.com/video/{aweme_id}",
                    "likes": stats.get("digg_count", 0),
                    "comments": stats.get("comment_count", 0),
                    "aweme_id": aweme_id,
                }
            )
            print(f"    {stats.get('digg_count', 0)}赞 {desc[:50]}")

    return articles


async def main():
    articles = await scrape_all()
    print(f"\n总计: {len(articles)}条")

    if articles:
        from collections import defaultdict

        data_file = os.path.join(SCRIPT_DIR, "data.json")
        with open(data_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        existing_ids = {str(a["id"]) for a in data["articles"]}
        merged = 0
        for a in articles:
            if str(a["id"]) not in existing_ids:
                data["articles"].append(a)
                existing_ids.add(str(a["id"]))
                merged += 1

        by_name = defaultdict(list)
        for a in data["articles"]:
            if a.get("source") == "blogger":
                by_name[a.get("blogger_name", "")].append(a)

        final = []
        for name, items in by_name.items():
            items.sort(key=lambda x: str(x.get("date", "")) + str(x.get("id", "")), reverse=True)
            good = [a for a in items if len(a.get("content_intro", "")) > 100]
            rest = [a for a in items if a not in good]
            final.extend((good + rest)[:3])

        data["articles"] = [a for a in data["articles"] if a.get("source") != "blogger"] + final

        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ 合并 +{merged}条, 保存到 data.json")
        for name in sorted(by_name.keys()):
            items = [a for a in final if a["blogger_name"] == name]
            print(f"  {name}: {len(items)}条")


if __name__ == "__main__":
    asyncio.run(main())
