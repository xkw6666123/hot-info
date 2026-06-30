#!/usr/bin/env python3
"""
深度风格学习系统
1. 从现有ASR文案中深度分析博主风格
2. 提取句式模板、词汇库、开头结尾模式
3. 基于学习到的模式生成更真实的灵感内容
"""
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
STYLE_FILE = os.path.join(os.path.dirname(__file__), "deep_style_learned.json")


def load_data():
    """加载数据"""
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def extract_sentence_patterns(text):
    """提取句式模板"""
    patterns = []
    sentences = re.split(r'[。！？]', text)
    for s in sentences:
        s = s.strip()
        if len(s) < 5 or len(s) > 100:
            continue
        # 提取句式结构（用占位符替换具体名词）
        pattern = s
        # 替换数字
        pattern = re.sub(r'\d+', '{数字}', pattern)
        # 替换日期
        pattern = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', '{日期}', pattern)
        pattern = re.sub(r'\d{1,2}月\d{1,2}日', '{日期}', pattern)
        # 替换人名（2-4个字的中文名）
        # pattern = re.sub(r'[\u4e00-\u9fff]{2,4}(?=说|问|答|表示|称)', '{人名}', pattern)
        patterns.append(pattern)
    return patterns


def extract_vocabulary(text):
    """提取词汇库"""
    words = {
        'transitions': [],  # 转折词
        'emotions': [],     # 情感词
        'interactions': [], # 互动词
        'connectors': [],   # 连接词
        'openers': [],      # 开头词
    }

    # 转折词
    transition_words = re.findall(r'不过|但是|其实|说实话|说真的|讲真的|说白了|说到底|归根结底|换句话说', text)
    words['transitions'].extend(transition_words)

    # 情感词
    emotion_words = re.findall(r'离谱|逆天|炸裂|惊呆|笑死|怒了|崩溃|破防|绷不住|绝了|牛|厉害|可怕|恐怖|搞笑|有意思|奇葩|迷惑', text)
    words['emotions'].extend(emotion_words)

    # 互动词
    interaction_words = re.findall(r'你们|大家|网友|评论区|点赞|分享|关注|觉得|认为|怎么看|遇到过|见过', text)
    words['interactions'].extend(interaction_words)

    # 连接词
    connector_words = re.findall(r'首先|然后|接着|最后|一方面|另一方面|不仅|而且|虽然|但是|因为|所以|如果|就|才|也|还|又|再|就', text)
    words['connectors'].extend(connector_words)

    # 开头词（每句话的前5个字）
    sentences = re.split(r'[。！？]', text)
    for s in sentences[:3]:
        s = s.strip()
        if len(s) >= 5:
            words['openers'].append(s[:5])

    return words


def extract_opening_patterns(text):
    """提取开头模式"""
    openings = []
    sentences = re.split(r'[。！？]', text)
    for s in sentences[:3]:
        s = s.strip()
        if len(s) >= 10:
            # 提取开头模式（前20个字）
            pattern = s[:20]
            # 替换具体名词为占位符
            pattern = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', '{日期}', pattern)
            pattern = re.sub(r'\d{1,2}月\d{1,2}日', '{日期}', pattern)
            openings.append(pattern)
    return openings


def extract_ending_patterns(text):
    """提取结尾模式"""
    endings = []
    sentences = re.split(r'[。！？]', text)
    for s in sentences[-3:]:
        s = s.strip()
        if len(s) >= 10:
            # 提取结尾模式（后20个字）
            pattern = s[-20:]
            endings.append(pattern)
    return endings


def analyze_blogger_style_deep(blogger_name, transcriptions):
    """深度分析单个博主的风格"""
    all_patterns = []
    all_words = defaultdict(list)
    all_openings = []
    all_endings = []

    for text in transcriptions:
        if len(text) < 100:
            continue

        # 提取句式模板
        patterns = extract_sentence_patterns(text)
        all_patterns.extend(patterns)

        # 提取词汇库
        words = extract_vocabulary(text)
        for k, v in words.items():
            all_words[k].extend(v)

        # 提取开头结尾
        openings = extract_opening_patterns(text)
        all_openings.extend(openings)

        endings = extract_ending_patterns(text)
        all_endings.extend(endings)

    if not all_patterns:
        return None

    # 统计高频句式
    pattern_counts = Counter(all_patterns)
    top_patterns = [p for p, c in pattern_counts.most_common(20) if c >= 1]

    # 统计高频词汇
    word_stats = {}
    for k, v in all_words.items():
        word_counts = Counter(v)
        word_stats[k] = [w for w, c in word_counts.most_common(10)]

    # 统计高频开头结尾
    opening_counts = Counter(all_openings)
    ending_counts = Counter(all_endings)

    style = {
        "blogger": blogger_name,
        "sample_count": len(transcriptions),
        "sentence_patterns": top_patterns[:10],
        "vocabulary": word_stats,
        "top_openings": [p for p, c in opening_counts.most_common(5)],
        "top_endings": [p for p, c in ending_counts.most_common(5)],
        "avg_length": sum(len(t) for t in transcriptions) // len(transcriptions),
    }

    return style


def learn_all_styles_deep():
    """深度学习所有博主的风格"""
    data = load_data()
    bloggers = [a for a in data.get("articles", []) if a.get("source") == "blogger"]

    # 按博主分组
    blogger_texts = {}
    for b in bloggers:
        name = b.get("blogger_name", "")
        ci = b.get("content_intro", "")
        if name and ci and len(ci) > 100:
            if name not in blogger_texts:
                blogger_texts[name] = []
            blogger_texts[name].append(ci)

    # 深度分析每位博主
    styles = {}
    for name, texts in blogger_texts.items():
        style = analyze_blogger_style_deep(name, texts)
        if style:
            styles[name] = style
            print(f"✅ {name}: {style['sample_count']}条样本, 平均{style['avg_length']}字")
            print(f"  句式模板: {len(style['sentence_patterns'])}个")
            print(f"  转折词: {style['vocabulary'].get('transitions', [])[:5]}")
            print(f"  情感词: {style['vocabulary'].get('emotions', [])[:5]}")
            print(f"  开头模式: {style['top_openings'][:3]}")

    # 保存
    with open(STYLE_FILE, "w", encoding="utf-8") as f:
        json.dump(styles, f, ensure_ascii=False, indent=2)

    print(f"\n已保存 {len(styles)} 位博主深度风格到 {STYLE_FILE}")
    return styles


def generate_inspiration_from_deep_style(topic, source, styles):
    """基于深度学习到的风格生成灵感"""
    import hashlib

    def pick(patterns, seed):
        if not patterns:
            return ""
        return patterns[abs(hash(seed)) % len(patterns)]

    today_str = datetime.now().strftime("%m月%d日")
    results = {}

    for blogger_name, style in styles.items():
        # 获取风格特征
        openings = style.get("top_openings", [])
        endings = style.get("top_endings", [])
        transitions = style.get("vocabulary", {}).get("transitions", [])
        emotions = style.get("vocabulary", {}).get("emotions", [])
        interactions = style.get("vocabulary", {}).get("interactions", [])
        patterns = style.get("sentence_patterns", [])

        # 生成开头
        opening = pick(openings, topic + blogger_name) if openings else ""
        if not opening:
            opening = f"{today_str}，"

        # 生成结尾
        ending = pick(endings, topic + blogger_name + "end") if endings else ""
        if not ending:
            ending = "你们觉得呢？评论区聊聊。"

        # 生成转折
        transition = pick(transitions, topic + blogger_name + "trans") if transitions else "不过"

        # 生成情感词
        emotion = pick(emotions, topic + blogger_name + "emo") if emotions else "有意思"

        # 生成互动词
        interaction = pick(interactions, topic + blogger_name + "inter") if interactions else "你们"

        # 根据博主风格生成内容
        if blogger_name == "网吧信息差":
            content = f"{opening}{topic}。这事儿一出来，网友们直接就绷不住了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有故事。但不管怎么说，这事儿确实挺{emotion}的。{interaction}遇到过类似的事吗？评论区分享一下。"
        elif blogger_name == "阿七大型纪录片":
            content = f"热点信息差，{topic}。这事儿一出来，网友们直接就炸锅了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有隐情。但不管怎么说，这事儿确实挺{emotion}的。{interaction}遇到过类似的事吗？评论区分享一下。"
        elif blogger_name == "陈先生":
            content = f"{topic}。这事儿一出来，直接把网友们整不会了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有故事。{interaction}怎么看？评论区聊聊。"
        elif blogger_name == "人类观察菌":
            content = f"今日热点信息快报。{topic}。这事儿一出来，网友们直接就炸锅了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有隐情。但不管怎么说，这事儿确实挺{emotion}的。{interaction}遇到过类似的事吗？评论区分享一下。"
        elif blogger_name == "沙漠一之雕":
            content = f"一夜之间发生了啥？{today_str}热点快报。第一条——{topic}。起因很简单，但后面发生的事完全出乎意料。事情是这样的：最早是——结果没过多久——然后今天上午——。大家现在最关心的问题是——这个问题的答案可能比你想的复杂。来评论区一人一句。"
        else:
            content = f"{opening}{topic}。{ending}"

        results[blogger_name] = content

    return results


def main():
    """主函数"""
    print("=== 深度风格学习 ===\n")

    # 学习风格
    styles = learn_all_styles_deep()

    if not styles:
        print("没有足够的样本数据")
        return

    # 生成示例灵感
    print("\n=== 示例灵感生成 ===\n")
    sample_topic = "张雪的一句是我们引发岛内热议"
    inspirations = generate_inspiration_from_deep_style(sample_topic, "百度热搜", styles)

    for blogger, content in inspirations.items():
        print(f"\n【{blogger}】")
        print(f"  {content[:150]}...")


if __name__ == "__main__":
    main()
