#!/usr/bin/env python3
"""批量提取博主视频 ASR 文案"""
import json, os, sys, time, re

os.environ['MIMO_API_KEY'] = 'tp-c03hkz73ublqqhz4q4ya5k75dwjh8igvzyf25h126nlhmack'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asr_extract import get_bilibili_content, get_douyin_content
try:
    from opencc import OpenCC
    cc = OpenCC('t2s')
except:
    cc = None

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
d = json.load(open(DATA, encoding='utf-8-sig'))
bloggers = [a for a in d['articles'] if a.get('source') == 'blogger']
short = [b for b in bloggers if len(b.get('content_intro', '')) < 200]

print(f'需要提取: {len(short)}/{len(bloggers)} 条')

updated = 0
for i, a in enumerate(short):
    url = a.get('url', '')
    name = a.get('blogger_name', '?')
    title = (a.get('title', '') or '')[:30]
    print(f'[{i+1}/{len(short)}] {name}: {title}...')

    try:
        if 'bilibili.com' in url:
            text = get_bilibili_content(url)
        elif 'douyin.com' in url:
            text = get_douyin_content(url)
        else:
            print('  跳过: 未知平台')
            continue

        if text and len(text) > 50:
            if cc:
                text = cc.convert(text)
            text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            a['content_intro'] = text[:2000]
            updated += 1
            print(f'  ✅ 成功: {len(text)} 字')
        else:
            print(f'  ❌ 内容太短: {len(text) if text else 0} 字')
    except Exception as e:
        print(f'  ❌ 失败: {e}')

    time.sleep(2)

print(f'\n结果: 更新 {updated}/{len(short)} 条')

if updated:
    tmp = DATA + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA)
    print('✅ data.json 已更新')

    import subprocess
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_js_data.py')])
    if r.returncode == 0:
        print('✅ index.html 已更新')
