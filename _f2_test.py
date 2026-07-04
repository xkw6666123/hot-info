# -*- coding: utf-8 -*-
"""F2 抖音博主视频抓取诊断（含代理修复）"""
import os, sys
from datetime import datetime

# ====== 代理修复（必须在 import f2 之前）======
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy']:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'
# 关键：设为空字符串让 httpx 跳过系统代理检测
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

with open('_valid_cookie.txt', 'r') as f:
    cookie_str = f.read().strip()

print(f'Cookie长度: {len(cookie_str)}')
print(f'代理: HTTP_PROXY={repr(os.environ.get("HTTP_PROXY"))}')

from f2.apps.douyin.handler import DouyinHandler
print('✅ F2 import 成功')

kwargs = {
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.douyin.com/',
    },
    'proxies': {'http://': None, 'https://': None},
    'timeout': 30,
    'cookie': cookie_str,
}

bloggers = [
    ('网吧信息差', 'MS4wLjABAAAAAeI9ck5yPPlaq1HYy-BxvwmVGxYvXtmO7rNOlZz7tUk'),
]

for name, sec_uid in bloggers:
    print(f'\n{"="*50}')
    print(f'博主: {name}')
    print(f'{"="*50}')
    try:
        dh = DouyinHandler(kwargs)
        # 查看方法签名
        import inspect
        sig = inspect.signature(dh.fetch_user_post_videos)
        print(f'方法签名: {sig}')
        
        # 用正确的参数调用
        result = dh.fetch_user_post_videos(sec_user_id=sec_uid, max_cursor=0, count=20)
        sc = result.get('status_code', 'N/A')
        print(f'status_code: {sc}')
        aweme_list = result.get('aweme_list', [])
        print(f'视频数: {len(aweme_list)}')
        
        if aweme_list:
            for i, v in enumerate(aweme_list[:8]):
                desc = v.get('desc', '?')[:60]
                ts = v.get('create_time', 0)
                dt = datetime.fromtimestamp(ts).strftime('%m/%d %H:%M') if ts else '?'
                stats = v.get('statistics', {})
                likes = stats.get('digg_count', '?')
                cmts = stats.get('comment_count', '?')
                shares = stats.get('share_count', '?')
                print(f'  [{i+1}] {dt} | ❤️{likes} 💬{cmts} 🔗{shares} | {desc}')
            
            latest_ts = aweme_list[0].get('create_time', 0)
            print(f'\n✅ 最新视频: {datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d %H:%M")}')
            print('✅ Cookie有效! F2工作正常!')
        else:
            print(f'❌ 空! status_msg={result.get("status_msg", "")}')
    except TypeError as te:
        print(f'参数错误: {te}')
        # 尝试不带关键字参数
        try:
            print('尝试其他调用方式...')
            result = dh.fetch_user_post_videos(sec_uid, 0, 20)
            sc = result.get('status_code', 'N/A')
            print(f'status_code: {sc}')
            aweme_list = result.get('aweme_list', [])
            print(f'视频数: {len(aweme_list)}')
        except Exception as e2:
            print(f'也失败了: {e2}')
    except Exception as e:
        print(f'ERR: {type(e).__name__}: {e}')

print('\n=== 诊断完成 ===')
