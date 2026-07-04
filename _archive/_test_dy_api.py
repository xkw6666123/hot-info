# -*- coding: utf-8 -*-
"""Direct Douyin Web API test v2"""
import urllib.request, urllib.error, json, browser_cookie3
from datetime import datetime

cj = browser_cookie3.chrome(domain_name='douyin.com')
cookie_str = '; '.join('{}={}'.format(c.name, c.value) for c in cj if 'douyin' in c.domain)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

bloggers = [
    ("网吧信息差", "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"),
]

for name, sec_uid in bloggers:
    print("=== {} ===".format(name))
    
    url = "https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={}&max_cursor=0&count=10&device_platform=webapp&aid=6383".format(sec_uid)
    req = urllib.request.Request(url,
        headers={
            'User-Agent': UA,
            'Referer': 'https://www.douyin.com/user/{}'.format(sec_uid),
            'Cookie': cookie_str,
        })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            text = raw.decode('utf-8', errors='replace')
            print("  Response status: {}".format(resp.status))
            print("  Response length: {}".format(len(text)))
            print("  First 300 chars: {}".format(text[:300]))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:500]
        print("  HTTP Error {}: {}".format(e.code, e.reason))
        print("  Body: {}".format(body))
    except Exception as e:
        print("  Error: {}".format(e))
