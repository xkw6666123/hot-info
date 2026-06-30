#!/usr/bin/env python3
"""
内容优化系统
1. 分析博主文案特征
2. 优化灵感生成
3. 持续学习改进
"""
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
ARCHIVE_FILE = os.path.join(os.path.dirname(__file__), "blogger_content_archive.json")
STYLE_FILE = os.path.join(os.path.dirname(__file__), "deep_style_learned.json")
ANALYSIS_FILE = os.path.join(os.path.dirname(__file__), "text_analysis.json")


def load_json(path):
    """加载JSON文件"""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path, data):
    """保存JSON文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_advanced_features(text):
    """提取高级文本特征"""
    features = {
        'length': len(text),
        'sentences': re.split(r'[。！？]', text),
        'sentence_count': 0,
        'avg_sentence_length': 0,
        'vocabulary_richness': 0,
        'emotional_intensity': 0,
        'interaction_level': 0,
        'storytelling_score': 0,
    }

    # 句子分析
    sentences = [s.strip() for s in features['sentences'] if len(s.strip()) > 5]
    features['sentence_count'] = len(sentences)
    if sentences:
        features['avg_sentence_length'] = sum(len(s) for s in sentences) // len(sentences)

    # 词汇丰富度
    words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
    unique_words = set(words)
    features['vocabulary_richness'] = len(unique_words) / max(len(words), 1)

    # 情感强度
    emotion_words = re.findall(r'离谱|逆天|炸裂|惊呆|笑死|怒了|崩溃|破防|绷不住|绝了|牛|厉害|可怕|恐怖|搞笑|有意思|奇葩|迷惑', text)
    features['emotional_intensity'] = len(emotion_words) / max(len(sentences), 1)

    # 互动程度
    interaction_words = re.findall(r'你们|大家|网友|评论区|点赞|分享|关注|觉得|认为|怎么看', text)
    features['interaction_level'] = len(interaction_words) / max(len(sentences), 1)

    # 故事性评分
    story_words = re.findall(r'起因|经过|结果|然后|接着|最后|一开始|后来|突然|没想到', text)
    features['storytelling_score'] = len(story_words) / max(len(sentences), 1)

    return features


def analyze_all_bloggers():
    """分析所有博主"""
    data = load_json(DATA_FILE)
    archive = load_json(ARCHIVE_FILE)

    # 合并data.json和archive中的文案
    all_content = defaultdict(list)

    # 从data.json
    for a in data.get("articles", []):
        if a.get("source") != "blogger":
            continue
        name = a.get("blogger_name", "")
        ci = a.get("content_intro", "")
        if name and ci and len(ci) > 100:
            all_content[name].append(ci)

    # 从archive
    for aweme_id, item in archive.items():
        name = item.get("blogger_name", "")
        ci = item.get("content_intro", "")
        if name and ci and len(ci) > 100:
            # 避免重复
            if ci not in all_content[name]:
                all_content[name].append(ci)

    # 分析每位博主
    results = {}
    for name, texts in all_content.items():
        features_list = []
        for text in texts:
            features = extract_advanced_features(text)
            features_list.append(features)

        if not features_list:
            continue

        # 汇总统计
        results[name] = {
            'sample_count': len(texts),
            'avg_length': sum(f['length'] for f in features_list) // len(features_list),
            'avg_sentences': sum(f['sentence_count'] for f in features_list) // len(features_list),
            'avg_sentence_length': sum(f['avg_sentence_length'] for f in features_list) // len(features_list),
            'vocabulary_richness': sum(f['vocabulary_richness'] for f in features_list) / len(features_list),
            'emotional_intensity': sum(f['emotional_intensity'] for f in features_list) / len(features_list),
            'interaction_level': sum(f['interaction_level'] for f in features_list) / len(features_list),
            'storytelling_score': sum(f['storytelling_score'] for f in features_list) / len(features_list),
            'last_analyzed': datetime.now().isoformat(),
        }

        print(f"✅ {name}: {len(texts)}条样本")
        print(f"  平均长度: {results[name]['avg_length']}字")
        print(f"  词汇丰富度: {results[name]['vocabulary_richness']:.2f}")
        print(f"  情感强度: {results[name]['emotional_intensity']:.2f}")
        print(f"  互动程度: {results[name]['interaction_level']:.2f}")
        print(f"  故事性: {results[name]['storytelling_score']:.2f}")

    return results


def optimize_inspirations(analysis):
    """基于分析结果优化灵感生成"""
    # 读取现有灵感
    data = load_json(DATA_FILE)
    inspirations = data.get("inspirations", [])

    if not inspirations:
        print("⚠️ 没有灵感数据")
        return

    # 分析每条灵感的质量
    quality_scores = []
    for insp in inspirations:
        score = 0
        for field in ['wangba', 'aqi', 'chen', 'guancha', 'shadi']:
            content = insp.get(field, '')
            if len(content) > 50:
                score += 1
            if len(content) > 100:
                score += 1
        quality_scores.append(score)

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    print(f"\n📊 灵感质量分析:")
    print(f"  总数: {len(inspirations)}")
    print(f"  平均质量分: {avg_quality:.1f}/10")

    # 识别低质量灵感
    low_quality = [i for i, s in enumerate(quality_scores) if s < 3]
    if low_quality:
        print(f"  ⚠️ 低质量灵感: {len(low_quality)}条")


def main():
    """主函数"""
    print("=== 内容优化系统 ===\n")

    # 1. 分析博主内容
    print("📊 分析博主内容...")
    analysis = analyze_all_bloggers()

    # 2. 保存分析结果
    save_json(ANALYSIS_FILE, analysis)
    print(f"\n✅ 分析结果已保存到 {ANALYSIS_FILE}")

    # 3. 优化灵感
    print("\n📊 分析灵感质量...")
    optimize_inspirations(analysis)

    print("\n✅ 优化完成！")


if __name__ == "__main__":
    main()
