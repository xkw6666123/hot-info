#!/usr/bin/env python3
"""
cntext 中文文本分析工具
情感分析、关键词提取、词频统计
"""
import json
import os
import re
from collections import Counter


def extract_keywords_jieba(text, top_n=10):
    """使用jieba提取关键词"""
    try:
        import jieba
        words = jieba.lcut(text)
        # 过滤停用词
        stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '吗', '吧', '啊', '呢'}
        words = [w for w in words if len(w) >= 2 and w not in stopwords]
        word_counts = Counter(words)
        return [w for w, c in word_counts.most_common(top_n)]
    except ImportError:
        # 如果没有jieba，使用简单的正则提取
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        words = [w for w in words if w not in stopwords]
        word_counts = Counter(words)
        return [w for w, c in word_counts.most_common(top_n)]


def analyze_sentiment(text):
    """情感分析"""
    # 正面情感词
    positive_words = ['好', '棒', '赞', '厉害', '牛', '优秀', '精彩', '感动', '开心', '快乐', '幸福', '成功', '胜利', '突破', '创新', '喜欢', '爱', '美', '妙', '强']
    # 负面情感词
    negative_words = ['坏', '差', '烂', '糟', '可怕', '恐怖', '离谱', '逆天', '炸裂', '崩溃', '怒', '骂', '打', '杀', '死', '失败', '错误', '恨', '厌', '烦', '苦', '痛']

    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)

    total = pos_count + neg_count
    if total == 0:
        return {'positive': 0, 'negative': 0, 'neutral': 1, 'sentiment': 'neutral'}

    pos_ratio = pos_count / total
    neg_ratio = neg_count / total

    if pos_ratio > 0.6:
        sentiment = 'positive'
    elif neg_ratio > 0.6:
        sentiment = 'negative'
    else:
        sentiment = 'neutral'

    return {
        'positive': pos_ratio,
        'negative': neg_ratio,
        'neutral': 1 - pos_ratio - neg_ratio,
        'sentiment': sentiment
    }


def analyze_readability(text):
    """可读性分析"""
    sentences = re.split(r'[。！？]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

    if not sentences:
        return {'avg_sentence_length': 0, 'sentence_count': 0, 'readability': 'unknown'}

    avg_length = sum(len(s) for s in sentences) / len(sentences)

    if avg_length < 15:
        readability = 'easy'
    elif avg_length < 30:
        readability = 'medium'
    else:
        readability = 'hard'

    return {
        'avg_sentence_length': avg_length,
        'sentence_count': len(sentences),
        'readability': readability
    }


def analyze_text(text):
    """综合文本分析"""
    return {
        'keywords': extract_keywords_jieba(text),
        'sentiment': analyze_sentiment(text),
        'readability': analyze_readability(text),
        'length': len(text),
    }


def analyze_blogger_texts():
    """分析博主文案"""
    data_file = os.path.join(os.path.dirname(__file__), '..', 'data.json')
    with open(data_file, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)

    bloggers = [a for a in data.get('articles', []) if a.get('source') == 'blogger']

    results = {}
    for b in bloggers:
        name = b.get('blogger_name', '')
        ci = b.get('content_intro', '')
        if not name or not ci or len(ci) < 100:
            continue

        if name not in results:
            results[name] = []

        analysis = analyze_text(ci)
        analysis['title'] = b.get('title', '')[:30]
        analysis['date'] = b.get('date', '')
        results[name].append(analysis)

    return results


def main():
    """主函数"""
    print("=== cntext 文本分析 ===\n")

    results = analyze_blogger_texts()

    for name, analyses in results.items():
        print(f"\n【{name}】")
        print(f"  样本数: {len(analyses)}")

        # 汇总关键词
        all_keywords = []
        for a in analyses:
            all_keywords.extend(a['keywords'])
        keyword_counts = Counter(all_keywords)
        top_keywords = [w for w, c in keyword_counts.most_common(10)]
        print(f"  关键词: {top_keywords[:5]}")

        # 汇总情感
        sentiments = [a['sentiment']['sentiment'] for a in analyses]
        sentiment_counts = Counter(sentiments)
        print(f"  情感分布: {dict(sentiment_counts)}")

        # 汇总可读性
        readability = [a['readability']['readability'] for a in analyses]
        readability_counts = Counter(readability)
        print(f"  可读性: {dict(readability_counts)}")

    # 保存结果
    output_file = os.path.join(os.path.dirname(__file__), '..', 'cntext_analysis.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析完成，结果已保存到 {output_file}")


if __name__ == "__main__":
    main()
