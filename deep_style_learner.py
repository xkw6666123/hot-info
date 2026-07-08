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
    """基于深度学习到的风格生成灵感 —— v2 更真实多样"""
    import hashlib, random, re

    def pick(patterns, seed):
        if not patterns:
            return ""
        return patterns[abs(hash(seed)) % len(patterns)]
    
    def pick_n(patterns, seed, n=2):
        if not patterns:
            return []
        rng = random.Random(abs(hash(seed)))
        pool = list(set(patterns))
        if len(pool) <= n:
            return pool
        return rng.sample(pool, min(n, len(pool)))

    # 清洗话题：去括号、去话题标签
    clean = re.sub(r'\[.*?\]', '', topic)
    clean = re.sub(r'#[^\s#]+', '', clean)
    clean = clean.strip()
    short_t = clean if len(clean) <= 20 else clean[:20] + "…"

    today_str = datetime.now().strftime("%m月%d日")
    results = {}

    for blogger_name, style in styles.items():
        openings = style.get("top_openings", [])
        endings = style.get("top_endings", [])
        transitions = style.get("vocabulary", {}).get("transitions", [])
        emotions = style.get("vocabulary", {}).get("emotions", [])
        interactions = style.get("vocabulary", {}).get("interactions", [])
        connectors = style.get("vocabulary", {}).get("connectors", [])

        trans = pick(transitions, topic + blogger_name + "tr") or "但"
        emo = pick(emotions, topic + blogger_name + "em") or "离谱"
        inter = pick(interactions, topic + blogger_name + "in") or "网友"
        end_phrase = pick(endings, topic + blogger_name + "end") or ""
        
        if blogger_name == "网吧信息差":
            seed_i = topic + 'wb'
            patterns = [
                # 大学生荒诞解构风
                f"{clean}。真的，我一开始以为是谁编的段子，结果一查，真有这事儿。{trans}说真的，这事儿搁谁身上都得懵。{inter}们如果遇到了，第一反应是什么？#青年创作者成长计划 #内容过于真实",
                f"不是，{short_t}？我反复确认了三遍，这事儿还真就发生在咱身边。{trans}最离谱的是什么呢——官方回应已经出来了，跟网友猜的完全不一样。{inter}们自己去看，我在评论区放链接。#大学生 #热点",
                f"OK下事儿。{clean}。{trans}表面上看起来是个段子，但你细品——每次这种事儿发生，背后都有个一模一样的逻辑。说白了，不是人出了问题，是规则出了问题。{inter}觉得呢？",
                f"说回今天的新闻，第一个事儿：{short_t}。{trans}这事儿最搞笑的不是事情本身，是各方的反应——甲方恨不得连夜删帖，乙方疯狂甩锅，第三方默默吃瓜。{inter}你们品，细品。",
                f"来来来，最近有个事儿真给我整笑了。{clean}。{trans}你以为这事儿就一个版本？不不不，版本A是官方的，版本B是当事人的，版本C是网友脑补的——三个版本三个世界。{inter}你们觉得哪个最接近真相？",
                f"{clean}。{trans}我说一句公道话——这事儿不是谁对谁错的问题，它是一个系统性的bug。别人不敢说，我来说。{inter}支持的扣1，反对的扣2。",
                f"今天有个新闻我必须得讲讲。{clean}。{trans}起因是这样的——过程是这样的——结果是——。你品，这三个'这样的'，哪个环节是可以避免的？{inter}告诉我。",
            ]
            content = pick(patterns, seed_i)
            
        elif blogger_name == "阿七大型纪录片":
            seed_i = topic + 'aq'
            patterns = [
                f"热点信息差。{clean}。起因是有位/{short_t}的事/在网上火了。{trans}本来以为是件小事，没成想后面越闹越大，各路回应一个比一个精彩。{inter}们你们觉得谁有理？评论区辩一辩。",
                f"热点信息差。{clean}。说真的，第一眼看的时候我以为是在看段子，第二眼才发现是新闻。{trans}事情是这样的——最开始是——然后是——转折出现在——现在的状态是——。{inter}们看完觉得哪个环节最离谱？",
                f"热点信息差。{clean}。这事儿真的，一波三折都不足以形容。{trans}第一波——第二波——第三波——。目前最新的进展是——但{inter}们不要急着下结论，证据链还没完整。",
                f"热点信息差。{short_t}。哥们儿，这事儿搁以前谁能信？{trans}但现在它就是真的。{inter}们别光看，把这条转给你那个还不相信的朋友。",
                f"热点信息差。{clean}。你以为你看的是新闻，其实是连续剧。{trans}今天是第三集，前两集在这里→。{inter}们追不追？我每集都给剪好了。",
                f"热点信息差。{clean}。第一集→第二集→现在第三集。这个剧情走向，好莱坞编剧都不敢这么写。{trans}更狠的是——当事人还出来说话了。{inter}去评论区看看，已经有课代表总结了。",
                f"热点信息差。{short_t}这事儿我必须说两句。{trans}很多人都没注意到一个关键细节——。这个细节才是整个事情的转折点。{inter}们再看看原视频，注意那个时间点。",
            ]
            content = pick(patterns, seed_i)
            
        elif blogger_name == "陈先生":
            seed_i = topic + 'ch'
            patterns = [
                f"大型纪录片之《{short_t}》持续为您播出。{clean}，讲真的，这个事发生的时候我一点都不意外。因为在这之前已经有信号了。{trans}只是没人把这三个信号连起来看——第一个——第二个——第三个——。连起来看就很清楚了。",
                f"今天讲一个现象级的新闻：{clean}。{trans}我翻了一下评论区，点赞最高的三条评论分别代表了三种完全不同的立场。有意思的不是他们说了什么，而是他们的点赞数——你会发现这场争论其实没有赢家。",
                f"《{short_t}》这部纪录片更新了。{clean}。说大不大说小不小，但我注意到的不是事情本身，是各方的反应。甲方说——乙方回应——第三方插了一句——你看出来了吗？这里面有一个很微妙的权力结构。",
                f"这波真的不讲武德。{clean}。{trans}我理解为什么很多人说不可能——因为按照常规思路这件事确实不可能。但是这次人家走的路跟你想象的不太一样。数据不会骗人，你自己去看。",
                f"来讲一个正在发生的变化：{clean}。{trans}很多人看新闻只看标题，但其实这条新闻背后有三个信号：第一，——第二，——第三，——。任何一个信号单独看都不算什么，三个信号一起出现——这就不是偶然了。",
            ]
            content = pick(patterns, seed_i)
            
        elif blogger_name == "人类观察菌":
            seed_i = topic + 'gc'
            patterns = [
                f"今日热点快报：{clean}。先说基本事实——目前可以确认的是——。然后有意思的部分来了：官方说的是A，当事人说的是B，网友说的是C。三个版本，三个世界。我不告诉你谁对谁错，我把所有能找到的公开信息放在下面，你自己判断。",
                f"一条热乎的新闻。{short_t}。{trans}根据目前已经公开的信息，我整理了这样一个时间线——最开始是——然后是——转折出现在——现在的状态是——。你看完这条时间线，有没有觉得哪里不对劲？评论区告诉我。",
                f"热点快报，先看数据：{clean}。{trans}说一下我注意到的三个细节，其他报道基本都只提了第一个。细节一——细节二——细节三——。这三个细节连起来，指向一个不太一样的方向。今天我不给结论，只呈现信息。",
                f"今天观察到一个有趣的现象：{short_t}。{clean}。{trans}我打开评论区看了前五十条——大概60%的人说——30%的人说——剩下10%在问今天午饭吃什么。这个比例本身就是一个信号。{inter}觉得这说明什么？",
                f"快报时间。{clean}。{trans}巴沙收集了公开信息整理了一下前后脉络：起因→发展→各方回应→最新进展。好了打出来给你们了。我今天不想评价，因为我觉得这件事的答案不在任何一方的说法里，在那些还没被说出来的信息里。",
                f"今日快报，注意一个容易被忽视的细节。{clean}。{trans}所有媒体的标题都在强调A，但真正的关键其实是B。为什么没人提B？因为B涉及到——所以大家默契地选择看不见。{inter}你能看到B吗？",
            ]
            content = pick(patterns, seed_i)
            
        elif blogger_name == "沙漠一之雕":
            seed_i = topic + 'sd'
            patterns = [
                f"一夜之间发生了啥？{today_str}热点快报。第一条——{clean}。起因很简单，但后面发生的事完全出乎意料。事情是这样的：最早是——结果没过多久——然后今天上午——。大家现在最关心的问题是——来评论区一人一句。",
                f"{today_str}热点开唠。昨天晚上到今天全网最热闹的新闻：{short_t}。给还没看的朋友用一句话说清楚——{clean}。{trans}如果你觉得这件事就是一个简单的A导致B，那可能要重新想想了。因为它后面的逻辑其实是一条链。",
                f"用两分钟给你补完今天的热搜，先说最火的一个：{short_t}。{clean}。{trans}目前我看到的最新情况是这样——但如果你往回翻时间线，会发现事情在三天前就已经有苗头了。为什么三天前没人关注？因为那时候信息还太碎，没人拼起来。我帮你拼好了。",
                f"来，今天的热点按时间串一下：{clean}。早上——下午——傍晚——。一天之内，事情变了三回。每回都不一样。你如果只看中午的报道，你会得出一个完全相反的结论。这就是为什么你需要信息差。",
                f"补一下今天的热搜。{clean}。先说结论：这件事现在还在发酵中，后面的走向还没定。但有三点是确定的——第一——第二——第三——。这三点不管后面怎么变都不会变，因为这是事实，不是观点。好，下一条——",
                f"来了来了，{today_str}时间线整理好了。{clean}。{trans}先捋时间——再捋各方回应——最后捋争议焦点——。捋完之后你会发现，整件事情的最高潮，其实是——。{inter}觉得呢？",
                f"{today_str}热乎的新闻。{short_t}。{clean}。我直接把时间线给你们列出来：🔹最开始——🔹然后——🔹转折——🔹最新——。不分析了，你们自己看。关注我，信息差不掉线。",
            ]
            content = pick(patterns, seed_i)
            
        else:
            content = f"{clean}。{trans}这事儿一出来，{inter}们直接就炸锅了。有人说这也太{emo}了，有人说这背后肯定有故事。但不管怎么说，这事儿确实值得关注。{inter}怎么看？评论区聊聊。"

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
