#!/usr/bin/env python3
"""
文本分析工具
1. 情感分析
2. 关键词提取
3. 词频统计
4. 风格特征分析
"""
import json
import os
import re
from collections import Counter

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
ANALYSIS_FILE = os.path.join(os.path.dirname(__file__), "text_analysis.json")


def load_data():
    """加载数据"""
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def extract_keywords(text, top_n=10):
    """提取关键词（基于词频）"""
    # 简单的中文分词（基于正则）
    words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
    # 过滤停用词
    stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
    words = [w for w in words if w not in stopwords and len(w) >= 2]
    word_counts = Counter(words)
    return [w for w, c in word_counts.most_common(top_n)]


def analyze_emotion(text):
    """情感分析（基于关键词）"""
    positive_words = ['好', '棒', '赞', '厉害', '牛', '优秀', '精彩', '感动', '开心', '快乐', '幸福', '成功', '胜利', '突破', '创新']
    negative_words = ['坏', '差', '烂', '糟', '可怕', '恐怖', '离谱', '逆天', '炸裂', '崩溃', '怒', '骂', '打', '杀', '死', '失败', '错误']
    neutral_words = ['说', '看', '想', '做', '去', '来', '有', '没有', '是', '不是']

    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)
    neu_count = sum(1 for w in neutral_words if w in text)

    total = pos_count + neg_count + neu_count
    if total == 0:
        return {'positive': 0, 'negative': 0, 'neutral': 0, 'dominant': 'neutral'}

    return {
        'positive': pos_count / total,
        'negative': neg_count / total,
        'neutral': neu_count / total,
        'dominant': 'positive' if pos_count > neg_count else 'negative' if neg_count > pos_count else 'neutral'
    }


def analyze_style(text):
    """分析文本风格"""
    sentences = re.split(r'[。！？]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

    return {
        'length': len(text),
        'sentence_count': len(sentences),
        'avg_sentence_length': sum(len(s) for s in sentences) // len(sentences) if sentences else 0,
        'has_question': '？' in text or '?' in text,
        'has_exclamation': '！' in text or '!' in text,
        'has_ellipsis': '……' in text or '...' in text,
        'has_numbers': bool(re.search(r'\d+', text)),
        'has_dialog': any(kw in text for kw in ['说', '问', '答', '讲', '聊']),
    }


def analyze_blogger_content():
    """分析所有博主内容"""
    data = load_data()
    bloggers = [a for a in data.get("articles", []) if a.get("source") == "blogger"]

    results = {}
    for b in bloggers:
        name = b.get("blogger_name", "")
        ci = b.get("content_intro", "")
        if not name or not ci or len(ci) < 100:
            continue

        if name not in results:
            results[name] = {
                'samples': [],
                'keywords': [],
                'emotions': [],
                'styles': [],
            }

        # 提取关键词
        keywords = extract_keywords(ci)
        results[name]['keywords'].extend(keywords)

        # 情感分析
        emotion = analyze_emotion(ci)
        results[name]['emotions'].append(emotion)

        # 风格分析
        style = analyze_style(ci)
        results[name]['styles'].append(style)

        # 保存样本
        results[name]['samples'].append({
            'title': b.get('title', '')[:30],
            'date': b.get('date', ''),
            'length': len(ci),
            'keywords': keywords[:5],
            'emotion': emotion['dominant'],
        })

    # 汇总统计
    summary = {}
    for name, data in results.items():
        keyword_counts = Counter(data['keywords'])
        top_keywords = [w for w, c in keyword_counts.most_common(10)]

        emotion_counts = Counter(e['dominant'] for e in data['emotions'])
        dominant_emotion = emotion_counts.most_common(1)[0][0] if emotion_counts else 'neutral'

        avg_length = sum(s['length'] for s in data['styles']) // len(data['styles']) if data['styles'] else 0
        avg_sentences = sum(s['sentence_count'] for s in data['styles']) // len(data['styles']) if data['styles'] else 0

        summary[name] = {
            'sample_count': len(data['samples']),
            'avg_length': avg_length,
            'avg_sentences': avg_sentences,
            'top_keywords': top_keywords,
            'dominant_emotion': dominant_emotion,
            'emotion_distribution': dict(emotion_counts),
            'samples': data['samples'],
        }

    return summary


def main():
    """主函数"""
    print("=== 文本分析 ===\n")

    summary = analyze_blogger_content()

    for name, stats in summary.items():
        print(f"\n【{name}】")
        print(f"  样本数: {stats['sample_count']}")
        print(f"  平均长度: {stats['avg_length']}字")
        print(f"  平均句数: {stats['avg_sentences']}")
        print(f"  关键词: {stats['top_keywords'][:5]}")
        print(f"  主导情感: {stats['dominant_emotion']}")
        print(f"  情感分布: {stats['emotion_distribution']}")

    # 保存分析结果
    with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析完成，结果已保存到 {ANALYSIS_FILE}")


if __name__ == "__main__":
    main()
