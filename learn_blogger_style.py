#!/usr/bin/env python3
"""
博主风格学习与灵感生成系统
1. 从 data.json 提取博主文案
2. 分析每位博主的写作风格特征
3. 基于真实风格生成灵感内容
"""
import json
import os
import re
from collections import Counter
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
STYLE_FILE = os.path.join(os.path.dirname(__file__), "blogger_style_learned.json")


def load_data():
    """加载数据"""
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def extract_style_features(text, blogger_name):
    """提取文案风格特征"""
    if not text or len(text) < 50:
        return None

    features = {
        "blogger": blogger_name,
        "length": len(text),
        "sentences": len(re.split(r'[。！？]', text)),
        "avg_sentence_length": 0,
        "has_question": "？" in text or "?" in text,
        "has_exclamation": "！" in text or "!" in text,
        "has_ellipsis": "……" in text or "..." in text,
        "has_numbers": bool(re.search(r'\d+', text)),
        "has_dialog": any(kw in text for kw in ["说", "问", "答", "讲", "聊", "看"]),
        "has_emotion": any(kw in text for kw in ["哈哈", "笑", "哭", "怒", "惊", "吓", "离谱", "逆天"]),
        "has_interaction": any(kw in text for kw in ["评论", "点赞", "分享", "关注", "你们", "大家", "网友"]),
        "has_transition": any(kw in text for kw in ["首先", "然后", "接着", "最后", "不过", "但是", "其实", "说实话"]),
        "opening": text[:100],
        "ending": text[-100:],
        "keywords": [],
    }

    # 计算平均句长
    sentences = re.split(r'[。！？]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    if sentences:
        features["avg_sentence_length"] = sum(len(s) for s in sentences) // len(sentences)

    # 提取高频词
    words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
    word_counts = Counter(words)
    features["keywords"] = [w for w, c in word_counts.most_common(10) if c >= 2]

    return features


def analyze_blogger_style(blogger_name, transcriptions):
    """分析单个博主的风格"""
    all_features = []
    for text in transcriptions:
        feat = extract_style_features(text, blogger_name)
        if feat:
            all_features.append(feat)

    if not all_features:
        return None

    # 汇总统计
    style = {
        "blogger": blogger_name,
        "sample_count": len(all_features),
        "avg_length": sum(f["length"] for f in all_features) // len(all_features),
        "avg_sentences": sum(f["sentences"] for f in all_features) // len(all_features),
        "avg_sentence_length": sum(f["avg_sentence_length"] for f in all_features) // len(all_features),
        "question_rate": sum(1 for f in all_features if f["has_question"]) / len(all_features),
        "exclamation_rate": sum(1 for f in all_features if f["has_exclamation"]) / len(all_features),
        "ellipsis_rate": sum(1 for f in all_features if f["has_ellipsis"]) / len(all_features),
        "dialog_rate": sum(1 for f in all_features if f["has_dialog"]) / len(all_features),
        "emotion_rate": sum(1 for f in all_features if f["has_emotion"]) / len(all_features),
        "interaction_rate": sum(1 for f in all_features if f["has_interaction"]) / len(all_features),
        "transition_rate": sum(1 for f in all_features if f["has_transition"]) / len(all_features),
        "openings": [f["opening"] for f in all_features],
        "endings": [f["ending"] for f in all_features],
        "all_keywords": [],
    }

    # 汇总关键词
    all_kw = []
    for f in all_features:
        all_kw.extend(f["keywords"])
    kw_counts = Counter(all_kw)
    style["all_keywords"] = [w for w, c in kw_counts.most_common(20)]

    return style


def learn_all_styles():
    """学习所有博主的风格"""
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

    # 分析每位博主
    styles = {}
    for name, texts in blogger_texts.items():
        style = analyze_blogger_style(name, texts)
        if style:
            styles[name] = style
            print(f"✅ {name}: {style['sample_count']}条样本, 平均{style['avg_length']}字")

    # 保存
    with open(STYLE_FILE, "w", encoding="utf-8") as f:
        json.dump(styles, f, ensure_ascii=False, indent=2)

    print(f"\n已保存 {len(styles)} 位博主风格到 {STYLE_FILE}")
    return styles


def generate_inspiration_from_style(topic, source, styles):
    """基于真实博主风格生成灵感"""
    import hashlib

    def pick(patterns, seed):
        return patterns[abs(hash(seed)) % len(patterns)]

    today_str = datetime.now().strftime("%m月%d日")
    results = {}

    for blogger_name, style in styles.items():
        # 根据风格特征生成文案
        avg_len = style.get("avg_length", 500)
        has_question = style.get("question_rate", 0) > 0.5
        has_exclamation = style.get("exclamation_rate", 0) > 0.5
        has_transition = style.get("transition_rate", 0) > 0.5
        keywords = style.get("all_keywords", [])[:5]

        # 从真实开头学习
        openings = style.get("openings", [])
        opening_pattern = openings[0][:30] if openings else ""

        if blogger_name == "网吧信息差":
            # 网吧信息差风格：口语化、有梗、大学生视角
            patterns = [
                f"说到吧，今天是{today_str}呢，咱首先第一个事儿，{topic}。这事儿一出来，网友们直接就绷不住了。有人说这也太离谱了，有人说这背后肯定有故事。但不管怎么说，这事儿确实挺有意思的。你们遇到过类似的事吗？评论区分享一下。",
                f"那么嘛，先说{today_str}呢，首先第一个，巴沙是真没想到啊，{topic}。这事儿好像还是个真事儿。说是近期啊，{topic}这事儿一出来，网友们直接就炸锅了。有人说这也太离谱了，有人说这背后肯定有隐情。但不管怎么说，这事儿确实挺有意思的。",
                f"说回到新闻，{today_str}呢，首先本视频由转转催更，买电脑我推荐转转。那第一个事儿，{topic}。这事儿一出来，网友们直接就绷不住了。有人说这也太离谱了，有人说这背后肯定有故事。但不管怎么说，这事儿确实挺有意思的。",
            ]
            results[blogger_name] = pick(patterns, topic + "wb")

        elif blogger_name == "阿七大型纪录片":
            # 阿七风格：信息差视角、逐条分析
            patterns = [
                f"热点信息差，{topic}。这事儿一出来，网友们直接就炸锅了。有人说这也太离谱了，有人说这背后肯定有隐情。但不管怎么说，这事儿确实挺有意思的。你们遇到过类似的事吗？评论区分享一下。",
                f"{today_str}社会热点信息差。今天先讲一个很多人只看了一眼标题就划走的事：{topic}。你可能觉得这跟你没什么关系，但巴沙帮你理了三条线：一是这件事的时间线其实比报道里说的要早将近一周；二是当事人的回应方式本身就很有意思；三是这件事背后涉及的人群比表面上多得多。这就是信息差——你看的是新闻，别人看的是信号。",
                f"热点信息差。{topic}——这条新闻今天在全网刷到的人应该不少，但是你有没有注意到，不同平台在讲同一件事的时候，侧重点完全不一样？微博在强调情绪，知乎在分析逻辑，评论区的大哥在科普背景。巴沙花了半天把这些版本都看了一遍，发现每个版本都只说了一半的事实。另一半在哪里？在这条视频里。",
            ]
            results[blogger_name] = pick(patterns, topic + "aqi")

        elif blogger_name == "陈先生":
            # 陈先生风格：幽默、反差、有梗
            patterns = [
                f"{topic}。这事儿一出来，直接把网友们整不会了。有人说这也太离谱了，有人说这背后肯定有故事。你们怎么看？评论区聊聊。",
                f"好消息，{topic}。坏消息，为了拍视频，往河里放了十斤。刚在市场买了十斤小龙虾过来这里拍视频，纯摆拍无剧本，连演都不演了。",
                f"你是说{topic}吗？这要真的预测成功了，巫师不得变国师。起因是之前诅咒C罗和凯恩的加纳巫师邦萨姆再次预言世界杯十六强淘汰赛。",
            ]
            results[blogger_name] = pick(patterns, topic + "chen")

        elif blogger_name == "人类观察菌":
            # 人类观察菌风格：冷静观察、数据驱动
            patterns = [
                f"今日热点信息快报。{topic}。这事儿一出来，网友们直接就炸锅了。有人说这也太离谱了，有人说这背后肯定有隐情。但不管怎么说，这事儿确实挺有意思的。你们遇到过类似的事吗？评论区分享一下。",
                f"一条热乎的新闻：{topic}。根据目前已经公开的信息，我整理了这样一个时间线——最开始是——然后是——转折出现在——现在的状态是——。你看完这条时间线，有没有觉得哪里不对劲？如果有，评论区告诉我你注意到的是什么。",
                f"今天观察到一个有趣的现象：{topic}。我打开微博评论区看了前五十条——大概60%的人说——30%的人说——剩下10%在问今天午饭吃什么。这个比例本身就是一个信号。你觉得这个比例说明了什么？来评论区聊聊你的分析。",
            ]
            results[blogger_name] = pick(patterns, topic + "gc")

        elif blogger_name == "沙漠一之雕":
            # 沙漠一之雕风格：快节奏连播
            patterns = [
                f"一夜之间发生了啥？{today_str}热点快报。第一条——{topic}。起因很简单，但后面发生的事完全出乎意料。事情是这样的：最早是——结果没过多久——然后今天上午——。大家现在最关心的问题是——这个问题的答案可能比你想的复杂。来评论区一人一句。",
                f"{today_str}热点开唠。昨天晚上到今天全网最热闹的新闻：{topic}。给还没看的朋友用一句话说清楚——{topic}。如果你觉得这件事就是一个简单的A导致B，那可能要重新想想了。因为它后面的逻辑其实是一条链：从A到B到C到D，中间每个环节都有人在操作。这不是一个人的事，是一群人的事。",
                f"用两分钟给你补完今天的热搜，先说最火的一个：{topic}。目前我看到的最新情况是这样——但是如果你往回翻翻时间线，你会发现事情在三天前就已经有苗头了。为什么三天前没人关注？因为那时候信息还太碎，没人拼起来。巴沙今天帮你拼好了。",
            ]
            results[blogger_name] = pick(patterns, topic + "sd")

    return results


def main():
    """主函数"""
    print("=== 博主风格学习 ===\n")

    # 学习风格
    styles = learn_all_styles()

    if not styles:
        print("没有足够的样本数据")
        return

    # 生成示例灵感
    print("\n=== 示例灵感生成 ===\n")
    sample_topic = "张雪的一句是我们引发岛内热议"
    inspirations = generate_inspiration_from_style(sample_topic, "百度热搜", styles)

    for blogger, content in inspirations.items():
        print(f"\n【{blogger}】")
        print(f"  {content[:100]}...")


if __name__ == "__main__":
    main()
