"""诊断 F2 为什么返回旧数据"""
import asyncio, browser_cookie3
from datetime import datetime

# 提取 cookie
cj = browser_cookie3.chrome(domain_name='douyin.com')
cookie_str = '; '.join(f'{c.name}={c.value}' for c in cj if 'douyin' in c.domain)
print("Cookie length:", len(cookie_str))
print("Has ttwid:", 'ttwid' in cookie_str)
print("Has sessionid:", 'sessionid' in cookie_str)

from f2.apps.douyin.handler import DouyinHandler

kwargs = {
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Referer': 'https://www.douyin.com/',
    },
    'proxies': {'http://': None, 'https://': None},
    'timeout': 15,
    'cookie': cookie_str,
}

bloggers = [
    ("网吧信息差", "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"),
]

async def test_one():
    name, sec_uid = bloggers[0]
    print(f"\n=== Testing {name} ===")
    count = 0
    async for data in DouyinHandler(kwargs).fetch_user_post_videos(sec_uid, 0, 0, 10, 10):
        raw = data._to_raw()
        vlist = data._to_list()
        aweme_list = raw.get('aweme_list', [])
        print(f"  Batch: got {len(aweme_list)} videos")
        for i, v in enumerate(aweme_list):
            lt = vlist[i] if i < len(vlist) else {}
            desc = (v.get('desc') or '')[:40]
            aid = v.get('aweme_id', '')
            ct = lt.get('create_time', '?')
            stats = v.get('statistics', {}) or {}
            digg = stats.get('digg_count', 0) or 0
            print(f"  [{count+1}] id={aid} time={ct} desc={desc} likes={digg}")
            count += 1
        if count >= 8:
            break
    print(f"\nTotal fetched: {count}")

asyncio.run(test_one())
