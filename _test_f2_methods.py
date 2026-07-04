# -*- coding: utf-8 -*-
"""Try F2 with different API endpoints to get fresh data"""
import asyncio, browser_cookie3, json
from datetime import datetime

cj = browser_cookie3.chrome(domain_name='douyin.com')
cookie_str = '; '.join('{}={}'.format(c.name, c.value) for c in cj if 'douyin' in c.domain)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

sec_uid = "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"
name = "网吧信息差"

# Try different F2 methods
from f2.apps.douyin.handler import DouyinHandler

kwargs_base = {
    'headers': {
        'User-Agent': UA,
        'Referer': 'https://www.douyin.com/',
    },
    'proxies': {'http://': None, 'https://': None},
    'timeout': 20,
    'cookie': cookie_str,
}

async def test_method(method_name, extra_kwargs=None):
    print("\n=== Method: {} ===".format(method_name))
    kw = dict(kwargs_base)
    if extra_kwargs:
        kw.update(extra_kwargs)
    
    handler = DouyinHandler(kw)
    count = 0
    try:
        async for data in handler.fetch_user_post_videos(sec_uid, 0, 0, 5, 5):
            raw = data._to_raw()
            vlist = data._to_list()
            aweme_list = raw.get('aweme_list', [])
            print("  Got {} videos".format(len(aweme_list)))
            for i, v in enumerate(aweme_list[:3]):
                lt = vlist[i] if i < len(vlist) else {}
                desc = (v.get('desc') or '')[:40]
                aid = str(v.get('aweme_id', ''))
                ct_val = lt.get('create_time', '?')
                stats = v.get('statistics', {}) or {}
                digg = stats.get('digg_count', 0) or 0
                print("  [{}] id={} time={} likes={} {}".format(count+1, aid, ct_val, digg, desc))
                count += 1
            break  # Just first page
    except Exception as e:
        print("  ERROR: {}".format(e))

async def main():
    # Test 1: Default params
    await test_method("Default (cursor=0, count=5)")
    
    # Test 2: With different version info
    await test_method("Newer version", {
        'headers': {**kwargs_base['headers'], **{
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        }}
    })
    
    # Test 3: Try fetch_user_videos alternative method
    print("\n=== Method: fetch_user_videos (alternative) ===")
    try:
        handler = DouyinHandler(kwargs_base)
        async for data in handler.fetch_user_videos(sec_uid, 0, 20):
            raw = data._to_raw()
            aweme_list = raw.get('aweme_list', [])
            print("  Got {} videos".format(len(aweme_list)))
            for v in aweme_list[:3]:
                desc = (v.get('desc') or '')[:40]
                ct = v.get('create_time', 0)
                dt = datetime.fromtimestamp(ct).strftime('%Y-%m-%d %H:%M') if ct else '?'
                aid = str(v.get('aweme_id', ''))
                print("  id={} time={} {}".format(aid, dt, desc))
            break
    except Exception as e:
        print("  ERROR: {}".format(e))

    # Test 4: Check if there's a way to force refresh
    # Look at what other methods DouyinHandler has
    print("\n=== Available DouyinHandler methods ===")
    handler_methods = [m for m in dir(DouyinHandler) if not m.startswith('_') and callable(getattr(DouyinHandler, m, None))]
    for m in handler_methods:
        if 'video' in m.lower() or 'user' in m.lower() or 'post' in m.lower() or 'feed' in m.lower():
            print("  - {}".format(m))

asyncio.run(main())
