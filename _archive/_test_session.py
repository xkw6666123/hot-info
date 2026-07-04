# -*- coding: utf-8 -*-
"""Try fetch_user_feed_videos and other alternatives + check if we can get sessionid from Chrome"""
import asyncio, browser_cookie3
from datetime import datetime

cj = browser_cookie3.chrome(domain_name='douyin.com')
cookie_str = '; '.join('{}={}'.format(c.name, c.value) for c in cj if 'douyin' in c.domain)

# Check if sessionid exists under a different domain pattern  
print("=== Checking all cookie domains ===")
all_domains = set(c.domain for c in cj)
for d in sorted(all_domains):
    print("  domain: {}".format(d))

# Check for session-like cookies with different names
print("\n=== Session-like cookies ===")
for c in cj:
    n = c.name.lower()
    if 'sess' in n or 'sid' in n or 'login' in n or 'auth' in n or 'token' in n or 'passport' in n:
        val = str(c.value)[:40]
        print("  {}={} [domain={}]".format(c.name, val, c.domain))

# Now try feed endpoint
print("\n\n=== Try fetch_user_feed_videos ===")
from f2.apps.douyin.handler import DouyinHandler

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
    handler = DouyinHandler(kwargs)
    
    # Try user profile first - might have updated info
    print("\n--- User Profile ---")
    try:
        async for data in handler.fetch_user_profile(sec_uid):
            raw = data._to_raw()
            user = raw.get('user', {})
            print("  nickname: {}".format(user.get('nickname', '?')))
            print("  uid: {}".format(user.get('uid', '?')))
            print("  sec_uid: {}".format(user.get('sec_uid', '?')))
            print("  follower_count: {}".format(user.get('follower_count', 0)))
            # Print all keys
            print("  Keys: {}".format(list(raw.keys())[:20]))
            break
    except Exception as e:
        print("  ERROR: {}".format(e))

asyncio.run(test())
