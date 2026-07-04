#!/usr/bin/env python3
"""抓取抖音博主最新视频"""
import asyncio
import json
import os
import sys

# 导入 F2
try:
    from f2.apps.douyin.handler import DouyinHandler
    print('F2 OK')
except ImportError as e:
    print(f'F2 fail: {e}')
    sys.exit(1)

# 博主配置
BLOGGER_SEC_UIDS = {
    '网吧信息差': 'MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv',
    '阿七大型纪录片': 'MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf',
    '陈先生': 'MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF',
    '人类观察菌': 'MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN',
}

# 读取 cookie
import browser_cookie3
cj = browser_cookie3.chrome(domain_name='douyin.com')
cookie_str = '; '.join(f'{c.name}={c.value}' for c in cj if 'douyin' in c.domain)
print(f'Cookie: {len(cookie_str)} chars')

kwargs = {
    'headers': {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.douyin.com/'},
    'proxies': {'http://': None, 'https://': None},
    'timeout': 10,
    'cookie': cookie_str,
}

async def fetch_bloggers():
    results = {}
    for name, sec_uid in BLOGGER_SEC_UIDS.items():
        print(f'Fetching {name}...')
        videos = []
        try:
            async for data in DouyinHandler(kwargs).fetch_user_post_videos(sec_uid, 0, 0, 20, 20):
                raw = data._to_raw()
                vlist = data._to_list()
                aweme_list = raw.get('aweme_list', [])
                for i, v in enumerate(aweme_list):
                    lt = vlist[i] if i < len(vlist) else {}
                    desc = (v.get('desc', '') or '').strip()
                    ct = lt.get('create_time', '') if lt else ''
                    aweme_id = str(v.get('aweme_id', ''))
                    stats = v.get('statistics', {}) or {}
                    digg = stats.get('digg_count', 0) or 0
                    comment = stats.get('comment_count', 0) or 0
                    videos.append({
                        'title': desc[:80],
                        'desc': desc,
                        'date': ct[:10] if ct else '',
                        'time': ct[11:16].replace('-', ':') if ct else '',
                        'aweme_id': aweme_id,
                        'url': f'https://www.douyin.com/video/{aweme_id}',
                        'likes': digg,
                        'comments': comment,
                    })
            videos.sort(key=lambda x: x.get('date', ''), reverse=True)
            results[name] = videos[:5]
            latest_date = videos[0].get('date', '') if videos else 'none'
            print(f'  {name}: {len(videos)} videos, latest: {latest_date}')
        except Exception as e:
            print(f'  {name} error: {e}')
    return results

if __name__ == '__main__':
    results = asyncio.run(fetch_bloggers())
    with open('_f2_latest.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print('\n=== Latest Videos ===')
    for name, videos in results.items():
        print(f'\n{name}:')
        for v in videos[:3]:
            print(f'  {v["date"]} | {v["title"][:40]} | likes:{v["likes"]}')
