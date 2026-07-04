# -*- coding: utf-8 -*-
"""F2 抖音博主视频抓取 - async 版本"""
import os, sys, asyncio
from datetime import datetime

# 代理修复
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy']:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

with open('_valid_cookie.txt', 'r') as f:
    cookie_str = f.read().strip()

print(f'Cookie长度: {len(cookie_str)}')

from f2.apps.douyin.handler import DouyinHandler

kwargs = {
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.douyin.com/',
    },
    'proxies': {'http://': None, 'https://': None},
    'timeout': 30,
    'cookie': cookie_str,
}

async def main():
    bloggers = [
        ('网吧信息差', 'MS4wLjABAAAAAeI9ck5yPPlaq1HYy-BxvwmVGxYvXtmO7rNOlZz7tUk'),
    ]
    
    for name, sec_uid in bloggers:
        print(f'\n{"="*50}')
        print(f'博主: {name}')
        print(f'{"="*50}')
        
        dh = DouyinHandler(kwargs)
        raw_videos = []
        
        try:
            async for data in dh.fetch_user_post_videos(sec_uid, 0, 0, 20, 20):
                # data 是 UserPostFilter 对象
                raw = data._to_raw()
                vlist = data._to_list()
                aweme_list = raw.get('aweme_list', [])
                
                for i, v in enumerate(aweme_list):
                    lt = vlist[i] if i < len(vlist) else {}
                    raw_videos.append((v, lt))
                    
            print(f'总共获取: {len(raw_videos)} 条视频')
            
            if raw_videos:
                for i, (v, lt) in enumerate(raw_videos[:8]):
                    desc = v.get('desc', '?')[:60]
                    ts = v.get('create_time', 0)
                    dt = datetime.fromtimestamp(ts).strftime('%m/%d %H:%M') if ts else '?'
                    stats = v.get('statistics', {})
                    likes = stats.get('digg_count', '?')
                    cmts = stats.get('comment_count', '?')
                    shares = stats.get('share_count', '?')
                    print(f'  [{i+1}] {dt} | ❤️{likes} 💬{cmts} 🔗{shares} | {desc}')
                
                latest_ts = raw_videos[0][0].get('create_time', 0)
                print(f'\n✅✅✅ 最新视频: {datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d %H:%M")}')
                print('✅✅✅ Cookie有效! F2完全正常工作!')
            else:
                print('❌ 没有获取到视频')
                
        except Exception as e:
            print(f'ERR: {type(e).__name__}: {e}')

asyncio.run(main())
print('\n=== 完成 ===')
