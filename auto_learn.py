#!/usr/bin/env python3
"""
自动学习脚本
- 每次运行时自动记录新的博主文案
- 更新学习文件
- 用于后续灵感库生成
"""

import json
import os
from datetime import datetime

DATA_FILE = 'data.json'
LEARN_FILE = 'blogger_content_learn.json'

def load_learn_content():
    """加载学习文案"""
    if os.path.exists(LEARN_FILE):
        with open(LEARN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_learn_content(content):
    """保存学习文案"""
    with open(LEARN_FILE, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

def main():
    """主函数"""
    print('=== 自动学习 ===')
    
    # 加载现有学习文案
    learn = load_learn_content()
    print('现有学习文案: ' + str(len(learn)) + '条')
    
    # 读取data.json
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 找到所有完整的博主文案
    new_count = 0
    for a in data.get('articles', []):
        if a.get('source') != 'blogger':
            continue
        
        ci = a.get('content_intro', '')
        if len(ci) < 200:
            continue
        
        # 检查是否已存在
        exists = False
        for c in learn:
            if c.get('url') == a.get('url'):
                exists = True
                break
        
        if not exists:
            learn.append({
                'blogger_name': a.get('blogger_name', ''),
                'date': a.get('date', ''),
                'title': a.get('title', ''),
                'content': ci,
                'url': a.get('url', ''),
                'word_count': len(ci),
                'learned_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            new_count += 1
            print('  新增: ' + a.get('blogger_name', '') + ' | ' + a.get('date', '') + ' | ' + str(len(ci)) + '字')
    
    # 保存
    save_learn_content(learn)
    
    print('\\n新增学习文案: ' + str(new_count) + '条')
    print('总学习文案: ' + str(len(learn)) + '条')

if __name__ == '__main__':
    main()
