#!/usr/bin/env python3
"""
灵感库学习与生成脚本
- 自动记录博主文案
- 分析风格特征
- 生成更真实的灵感库
"""

import json
import os
from datetime import datetime
from opencc import OpenCC

cc = OpenCC('t2s')

# 学习文案文件
LEARN_FILE = 'blogger_content_learn.json'
DATA_FILE = 'data.json'

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

def extract_style_features(content):
    """提取文案风格特征"""
    text = content.get('content', '')
    name = content.get('blogger_name', '')
    
    features = {
        'blogger': name,
        'length': len(text),
        'has_question': '？' in text or '?' in text,
        'has_exclamation': '！' in text or '!' in text,
        'has_ellipsis': '……' in text or '...' in text,
        'has_dialog': any(kw in text for kw in ['说', '问', '答', '讲', '聊']),
        'has_emotion': any(kw in text for kw in ['哈哈', '笑', '哭', '怒', '惊', '吓']),
        'has_interaction': any(kw in text for kw in ['评论', '点赞', '分享', '关注', '你们']),
        'opening': text[:50] if len(text) > 50 else text,
        'ending': text[-50:] if len(text) > 50 else text,
    }
    
    return features

def analyze_styles():
    """分析所有学习文案的风格"""
    learn = load_learn_content()
    
    styles = {}
    for c in learn:
        name = c.get('blogger_name', '')
        if name not in styles:
            styles[name] = {
                'count': 0,
                'avg_length': 0,
                'features': [],
                'openings': [],
                'endings': [],
            }
        
        features = extract_style_features(c)
        styles[name]['count'] += 1
        styles[name]['avg_length'] += features['length']
        styles[name]['features'].append(features)
        styles[name]['openings'].append(features['opening'])
        styles[name]['endings'].append(features['ending'])
    
    # 计算平均值
    for name in styles:
        if styles[name]['count'] > 0:
            styles[name]['avg_length'] = styles[name]['avg_length'] // styles[name]['count']
    
    return styles

def generate_inspiration(event, style_name, styles):
    """基于风格生成灵感库文案"""
    title = event.get('title', '')
    summary = event.get('summary', '')
    today = datetime.now().strftime('%m月%d日')
    
    # 提取摘要的关键信息
    lines = summary.split('。')
    main_info = '。'.join(lines[:2]) if len(lines) > 2 else summary
    
    # 根据风格生成文案
    if style_name == '沙漠一之雕':
        # 快报连播风格
        content = f'''一夜发生了啥？{today}热点快报，先唠第一件事。

{title}。

{main_info}。

这事儿一出来，网友们都炸锅了。有人说这是好事，也有人说这背后肯定有隐情。但不管怎么说，这件事确实引起了大家的广泛关注。

评论区聊聊你的看法，你觉得这事儿到底咋回事？'''
    
    elif style_name == '网吧信息差':
        # 口语化叙事风格
        content = f'''{today}呢，首先第一一件事。

{title}。

{main_info}。

这事儿一出来，网友们都炸锅了。有人说这也太离谱了，有人说这背后肯定有故事。但不管怎么说，这事儿确实挺有意思的。

你们遇到过类似的事吗？评论区分享一下。'''
    
    elif style_name == '陈先生':
        # 简短精炼风格
        content = f'''{title}。

{main_info}。

这事儿一出来，直接把网友们整不会了。有人说这也太离谱了，有人说这背后肯定有故事。

你们怎么看？评论区聊聊。'''
    
    elif style_name == '人类观察菌':
        # 热点信息快报风格
        content = f'''今日热点信息快报。

{title}。

{main_info}。

这事儿一出来，网友们都开始讨论了。有人说这很正常，有人说这太奇葩了。但不管怎么说，这事儿确实引起了大家的关注。

你们怎么看？评论区聊聊。'''
    
    elif style_name == '阿七大型纪录片':
        # 信息差搬运风格
        content = f'''热点信息差。

{title}。

{main_info}。

这事儿一出来，网友们都炸锅了。有人说这也太离谱了，有人说这背后肯定有故事。但不管怎么说，这事儿确实挺有意思的。

你们遇到过类似的事吗？评论区分享一下。'''
    
    else:
        # 默认风格
        content = f'''{title}。

{main_info}。

这事儿一出来，网友们都开始讨论了。有人说这很正常，有人说这太奇葩了。但不管怎么说，这事儿确实引起了大家的关注。

你们怎么看？评论区聊聊。'''
    
    return content

def main():
    """主函数"""
    print('=== 灵感库学习与生成 ===')
    
    # 分析风格
    styles = analyze_styles()
    print('分析了 ' + str(len(styles)) + ' 种博主风格')
    
    for name, style in styles.items():
        print('  ' + name + ': ' + str(style['count']) + '条, 平均' + str(style['avg_length']) + '字')
    
    # 读取热点数据
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 选择热点事件
    hot_events = []
    for a in data.get('articles', [])[:50]:
        source = a.get('source', '')
        title = a.get('title', '')
        summary = a.get('summary', '')
        
        if source in ['微博', '百度热搜', '贴吧', '今日头条', '抖音']:
            if len(title) > 5 and len(summary) > 50:
                skip_keywords = ['习近平', '总书记', '朝鲜', '金正恩', '国事访问']
                if any(kw in title or kw in summary for kw in skip_keywords):
                    continue
                hot_events.append({
                    'title': title,
                    'summary': summary,
                    'source': source,
                    'likes': a.get('likes', 0),
                    'comments': a.get('comments', 0)
                })
    
    hot_events.sort(key=lambda x: x.get('likes', 0) + x.get('comments', 0), reverse=True)
    selected = hot_events[:10]
    
    # 生成灵感库
    inspirations = []
    style_names = list(styles.keys())
    
    for i, event in enumerate(selected):
        style_name = style_names[i % len(style_names)]
        content = generate_inspiration(event, style_name, styles)
        
        inspirations.append({
            'topic': event['title'],
            'source': event['source'],
            'blogger_name': style_name,
            'content': content,
            'style': style_name,
            'word_count': len(content),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # 更新data.json
    data['inspirations'] = inspirations
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print('\\n生成了 ' + str(len(inspirations)) + ' 条灵感库文案')
    
    print('\\n=== 灵感库预览 ===')
    for i, ins in enumerate(inspirations[:5]):
        print('\\n' + str(i+1) + '. [' + ins['style'] + '] ' + ins['topic'][:30])
        print('   字数: ' + str(ins['word_count']))
        print('   内容: ' + ins['content'][:100] + '...')

if __name__ == '__main__':
    main()
