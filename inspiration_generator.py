#!/usr/bin/env python3
"""
基于真实博主文案生成高质量灵感（final）
- 从 archive 学习情感词、连接词
- 手工定义每个博主的开场/过渡/口头禅（避免直接拼接原片段）
- 围绕热点话题重写，内容更具体、不空洞
- 按爆火潜力排序
"""
import json, os, re, random
from datetime import datetime
from collections import Counter, defaultdict

WORK = r"D:\AI\hotinfo\hot-info"
DATA_FILE = os.path.join(WORK, "data.json")
ARCHIVE_FILE = os.path.join(WORK, "blogger_content_archive.json")
STYLE_FILE = os.path.join(WORK, "deep_style_learned.json")

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def remove_duplicates(text, min_len=15):
    if not text:
        return text
    parts = re.split(r'([。！？\n])', text)
    sentences = []
    i = 0
    while i < len(parts):
        s = parts[i]
        if i + 1 < len(parts) and parts[i+1] in '。！？\n':
            s += parts[i+1]
            i += 2
        else:
            i += 1
        if s.strip():
            sentences.append(s)
    seen = set()
    clean = []
    for s in sentences:
        key = re.sub(r'\s+', '', s)
        if len(key) >= min_len and key in seen:
            continue
        seen.add(key)
        clean.append(s)
    return "".join(clean)

def clean_archive(archive):
    """清洗归档，过滤广告和低质量文案"""
    by_blogger = defaultdict(list)
    for aweme_id, item in archive.items():
        name = item.get("blogger_name", "")
        ci = item.get("content_intro", "")
        if not name or not ci or len(ci) < 200:
            continue
        if any(kw in ci for kw in ["追觅", "京东", "淘宝", "拼多多", "转转", "本视频由", "广告", "点击链接", "优惠券", "下单", "京东购物"]):
            continue
        ci = remove_duplicates(ci)
        if len(ci) < 200:
            continue
        by_blogger[name].append(ci)
    for name in by_blogger:
        by_blogger[name].sort(key=lambda x: len(x), reverse=True)
        by_blogger[name] = by_blogger[name][:10]
    return by_blogger

def extract_style_tokens(by_blogger):
    """从真实文案中提取：情感词、连接词"""
    styles = {}
    for name, texts in by_blogger.items():
        all_text = "\n".join(texts)
        # 情感词（扩大词表）
        emotions = re.findall(r'离谱|逆天|炸裂|绷不住|笑死|绝了|破防|迷惑|惊人|意外|搞笑|有意思|难绷|抽象|整不会|难评|无语|绷不住|头大|离谱|震惊|沉默|窒息|魔幻|荒唐|草率|离谱', all_text)
        # 连接词/转折词
        connectors = re.findall(r'不过|但是|其实|说实话|说白了|然而|可是|话说回来|说到底|究其根本|首先|然后|接着|最后', all_text)
        styles[name] = {
            "emotions": [e for e, _ in Counter(emotions).most_common(8)] or ["离谱"],
            "connectors": [c for c, _ in Counter(connectors).most_common(6)] or ["不过"],
        }
    return styles

# 每位博主的手工风格库：多模板变体，避免同质化
BLOGGER_STYLE = {
    "网吧信息差": {
        "templates": [
            "{opening}，{topic}。这事儿一出来，网友们直接绷不住了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有故事。{question}",
            "{opening}，今天第一个事儿：{topic}。{transition}，这操作属实有点迷，网友们都整不会了。{question}",
            "{opening}，咱就是说，{topic}这事儿，{transition}，真有点{emotion}。{question}",
            "{opening}，{topic}。{transition}，这事儿一出来，评论区直接炸了。{question}",
            "{opening}，今天聊一个{emotion}的事儿：{topic}。{transition}，很多网友都表示看不懂。{question}",
        ],
    },
    "阿七大型纪录片": {
        "templates": [
            "{opening}{topic}。{transition}，你只刷一条短视频，很容易忽略这件事的关键节点。不同平台讲的角度完全不一样：有人看到情绪，有人看到逻辑，还有人看到背景。{question}",
            "{opening}{topic}。{transition}，这件事水比表面深。我帮你把几个版本拼在一起，发现信息差就出来了。{question}",
            "{opening}先讲一个很多人只看了一眼标题就划走的事：{topic}。{transition}，如果你只关注情绪，会漏掉最重要的信号。{question}",
            "{opening}{topic}。{transition}，这个事儿背后的人群和节点，比标题本身更值得注意。{question}",
            "{opening}热点信息差，{topic}。{transition}，不同报道的侧重点完全不同，合起来看才能接近全貌。{question}",
        ],
    },
    "陈先生": {
        "templates": [
            "{topic}。{transition}，直接把网友们整不会了。{question}",
            "{topic}。{transition}，反转来得比预想的快。{question}",
            "{topic}。{transition}，这操作属实有点迷。{question}",
            "看到{topic}这事儿，{transition}，属实是有点{emotion}。{question}",
            "{topic}。{transition}，网友们的评论比事情本身还精彩。{question}",
        ],
    },
    "人类观察菌": {
        "templates": [
            "{opening}{topic}。{transition}，这件事的细节比标题丰富得多。我整理了一下公开信息的时间线，发现几个容易被忽略的点。{question}",
            "{opening}{topic}。{transition}，如果只刷短视频，你很容易错过这件事的关键信息。{question}",
            "{opening}{topic}。{transition}，我把能找到的公开信息串了一下，发现事情比标题更复杂。{question}",
            "{opening}观察到一个现象：{topic}。{transition}，数据和时间线比观点更值得关注。{question}",
            "{opening}{topic}。{transition}，这个事儿最值得看的是各方反应，而不是单一说法。{question}",
        ],
    },
    "沙漠一之雕": {
        "templates": [
            "{opening}第一条——{topic}。{transition}，目前这件事还在发酵。{question}",
            "{opening}先唠第一个：{topic}。{transition}，后续还在跟进。{question}",
            "{opening}第一条新闻：{topic}。{transition}，大家最关心的后续还在更新。{question}",
            "{opening}一夜之间发生了啥？先讲{topic}。{transition}，这件事还在持续发酵。{question}",
            "{opening}{topic}。{transition}，这条目前关注度最高，后续值得盯一下。{question}",
        ],
    },
}

OPENINGS = {
    "网吧信息差": ["那么嘛，先说今天呢", "说到吧，今天呢", "说回到新闻，今天呢", "各位，今天呢", "咱就是说"],
    "阿七大型纪录片": ["{today}社会热点信息差。", "热点信息差。", "今天讲一个信息差。", "{today}，巴沙帮你理一下热点。"],
    "陈先生": [""],
    "人类观察菌": ["今日热点信息快报。", "今天观察到一个现象。", "热点信息快报。"],
    "沙漠一之雕": ["一夜之间发生了啥？{today}热点快报。", "{today}热点开唠。", "{today}热点快报。"],
}

def extract_topic_keywords(topic):
    topic = re.sub(r'#\S+', '', topic)
    # 去掉尾部标点后的完整短标题
    clean = topic.strip('，。！？；、:： ')
    # 如果太长，取第一个短句或前12字
    if len(clean) <= 15:
        return clean
    for sep in '，。！？；、:： ':
        idx = clean.find(sep)
        if 3 <= idx <= 15:
            return clean[:idx]
    return clean[:12]

def generate_for_blogger(name, style, topic, source):
    """基于风格库生成新内容，不拼接原片段"""
    today = datetime.now().strftime("%m月%d日")
    seed = f"{topic}_{name}_{random.randint(0, 1000)}"
    bs = BLOGGER_STYLE.get(name, BLOGGER_STYLE["网吧信息差"])
    templates = bs["templates"]
    random.seed(seed)
    template = random.choice(templates)
    
    opening = random.choice(OPENINGS.get(name, [""]))
    opening = opening.replace("{today}", today)
    topic_kw = extract_topic_keywords(topic)
    emotion = random.choice(style.get("emotions", ["离谱"]))
    transition = random.choice(style.get("connectors", ["不过"]))
    question = random.choice(["你们怎么看？", "评论区聊聊。", "你怎么看？"])
    
    return template.format(
        opening=opening,
        today=today,
        topic=topic,
        topic_kw=topic_kw,
        emotion=emotion,
        transition=transition,
        question=question
    )

def douyin_score(a):
    import math
    score = 0
    title = a.get("title", "")
    likes = a.get("likes", 0) or 0
    comments = a.get("comments", 0) or 0
    source = a.get("source", "")
    if likes > 0:
        score += min(35, math.log2(likes + 1) * 2)
    if comments > 0:
        score += min(25, math.log2(comments + 1) * 1.8)
    for w in ['泪崩', '震惊', '怒了', '崩溃', '炸裂', '反转', '意外', '惊人', '离谱', '逆天', '破防']:
        if w in title:
            score += 12
            break
    for w in ['回应', '道歉', '曝光', '争议', '投诉', '维权', '实名举报', '偷税', '造假']:
        if w in title:
            score += 10
            break
    clean = re.sub(r'\[.*?\]|#\S+', '', title).strip()
    if len(clean) <= 12: score += 10
    elif len(clean) <= 20: score += 6
    source_boost = {'百度热搜': 8, '微博': 7, '知乎': 6, 'bilibili': 6, '今日头条': 5}
    score += source_boost.get(source, 2)
    return score

def select_hot_topics(data, n=50):
    articles = [a for a in data.get("articles", []) if a.get("source") != "blogger"]
    seen = set()
    unique = []
    for a in sorted(articles, key=douyin_score, reverse=True):
        t = a.get("title", "")
        if t and t not in seen:
            seen.add(t)
            unique.append(a)
    result = []
    src_count = defaultdict(int)
    for a in unique:
        src = a.get("source", "其他")
        if src_count[src] < 8 and len(result) < n:
            result.append(a)
            src_count[src] += 1
    return result

def main():
    print("=== 基于真实文案的灵感生成 ===\n")
    data = load_json(DATA_FILE)
    archive = load_json(ARCHIVE_FILE) if os.path.exists(ARCHIVE_FILE) else {}
    
    by_blogger = clean_archive(archive)
    styles = extract_style_tokens(by_blogger)
    print(f"学习样本: {sum(len(v) for v in by_blogger.values())} 条文案")
    for name, style in styles.items():
        print(f"  {name}: {len(style['emotions'])}情感词, {len(style['connectors'])}连接词")
    
    hot_topics = select_hot_topics(data, n=50)
    print(f"\n选中 {len(hot_topics)} 个热点话题\n")
    
    inspirations = []
    for a in hot_topics:
        topic = a.get("title", "")
        source = a.get("source", "")
        if not topic:
            continue
        insp = {
            "topic": topic,
            "source": source,
            "blogger_name": a.get("blogger_name", ""),
            "score": douyin_score(a),
        }
        for name in ["网吧信息差", "阿七大型纪录片", "陈先生", "人类观察菌", "沙漠一之雕"]:
            style = styles.get(name, {"emotions": ["离谱"], "connectors": ["不过"]})
            content = generate_for_blogger(name, style, topic, source)
            key = {"网吧信息差": "wangba", "阿七大型纪录片": "aqi", "陈先生": "chen", "人类观察菌": "guancha", "沙漠一之雕": "shadi"}.get(name, name)
            insp[key] = content
        inspirations.append(insp)
    
    inspirations.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    data["inspirations"] = inspirations
    data["updated_at"] = datetime.now().isoformat()
    save_json(DATA_FILE, data)
    save_json(STYLE_FILE, styles)
    
    print(f"\n✅ 已生成 {len(inspirations)} 条灵感并更新 data.json")
    print(f"   前3条热点: {', '.join([i['topic'][:15] for i in inspirations[:3]])}")

if __name__ == "__main__":
    main()
