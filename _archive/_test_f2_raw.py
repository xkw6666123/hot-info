# -*- coding: utf-8 -*-
"""Test F2 with more params and check raw response"""
import asyncio, browser_cookie3, json, sys

cj = browser_cookie3.chrome(domain_name='douyin.com')
cookie_str = '; '.join('{}={}'.format(c.name, c.value) for c in cj if 'douyin' in c.domain)

# Check key cookies
for name in ['ttwid', 'sessionid', 'passport_csrf_token', 'odin_tt']:
    val = [c.value for c in cj if c.name == name]
    if val:
        print("  Cookie {}: {}...{}".format(name, val[0][:20], val[0][-10:] if len(val[0]) > 30 else val[0]))
    else:
        print("  Cookie {}: MISSING".format(name))

from f2.apps.douyin.handler import DouyinHandler
from f2.log import logger

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

kwargs = {
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Referer': 'https://www.douyin.com/',
    },
    'proxies': {'http://': None, 'https://': None},
    'timeout': 20,
    'cookie': cookie_str,
}

sec_uid = "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"

async def test():
    print("\n=== F2 fetch with params (cursor=0, count=20) ===")
    handler = DouyinHandler(kwargs)
    count = 0
    async for data in handler.fetch_user_post_videos(sec_uid, 0, 0, 20, 20):
        raw = data._to_raw()
        vlist = data._to_list()
        aweme_list = raw.get('aweme_list', [])
        # Also print raw keys to understand structure
        print("Raw top-level keys: {}".format(list(raw.keys())[:15]))
        if aweme_list:
            v = aweme_list[0]
            print("Video keys: {}".format(list(v.keys())[:20]))
            ct = v.get('create_time', 0)
            print("create_time type={} value={}".format(type(ct), ct))
        for i, v in enumerate(aweme_list[:3]):
            lt = vlist[i] if i < len(vlist) else {}
            desc = (v.get('desc') or '')[:40]
            aid = str(v.get('aweme_id', ''))
            ct_val = lt.get('create_time', '?')
            stats = v.get('statistics', {}) or {}
            digg = stats.get('digg_count', 0) or 0
            print("  [{}] id={} time={} desc={} likes={}".format(count+1, aid, ct_val, desc, digg))
            count += 1
        break  # Just first batch
    print("\nTotal: {}".format(count))

asyncio.run(test())
