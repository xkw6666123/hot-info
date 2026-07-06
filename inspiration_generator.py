#!/usr/bin/env python3
"""
灵感生成器 v4 —— 基于博主创作指南 + 真实文案学习
- 每位博主独立的写作规则（标题公式、开头模板、禁区）
- 灵感数量由爆火潜力决定，不限于50
- 生成的文案像真人写的，不是模板填充
"""
import json, os, re, random
from datetime import datetime
from collections import Counter, defaultdict

WORK = r"D:\AI\hotinfo\hot-info"
DATA_FILE = os.path.join(WORK, "data.json")
ARCHIVE_FILE = os.path.join(WORK, "blogger_content_archive.json")

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# ═══════════════════════════════════════════════════════
#  博主创作指南（基于真实文案手动提炼）
# ═══════════════════════════════════════════════════════

BLOGGER_GUIDE = {
    "网吧信息差": {
        "identity": "大学生群体情绪代言人，用荒诞解构日常",
        "title_rules": [
            "悬念型：{网络热词} {动作/状态} {反转}，例：拼叔叔当年说的一刀一刀 难不成是真的！",
            "共情型：{重复词} {重复词} 要我也{动作}，例：能理解 能理解 要我也骂",
            "疑问型：古风词+？，例：此乃？何物？",
        ],
        "opening_style": [
            "那么嘛，先说{slogan}，首先第一个事儿，{topic}。",
            "说回到新闻，{slogan}，咱就是说，{topic}。",
            "说到吧，今天是{slogan}，首先第一个，巴沙是真没想到啊，{topic}。",
        ],
        "phrases": ["欧亚这", "那听到这儿", "那我说白了", "OK下事儿", "这年头真是"],
        "forbidden": ["不用Emoji", "不说教/不用长辈口吻", "不写长文案", "不蹭社会新闻热点"],
        "tags": "#青年创作者成长计划 #大学生 #搞笑 #内容过于真实 #热点",
        "signature": "评论区聊聊",
    },
    "阿七大型纪录片": {
        "identity": "信息差调查记者，帮观众拼出完整图景",
        "title_rules": [
            "{日期}社会热点信息差 —— {话题1}、{话题2}、{话题3}等",
            "热点信息差，{一句话总结}",
        ],
        "opening_style": [
            "{today}社会热点信息差。{topic}。",
            "热点信息差，{topic}。",
            "今天讲一条很多人只看了一眼标题就划走的事：{topic}。",
        ],
        "phrases": ["划重点", "你看的是新闻，有人看的是信号", "信息差就在这", "OK下一件事"],
        "forbidden": ["不说废话", "不站队表态度", "不写情绪化标题"],
        "tags": "#热点 #社会热点信息差 #信息差",
        "signature": "好了，信息给你了。",
    },
    "陈先生": {
        "identity": "商业纪录片旁白风格，宏大叙事+反转幽默",
        "title_rules": [
            "{话题}。{反转}。",
            "大型纪录片之《{关键词}》持续为您播出",
            "你是说{话题}吗？",
        ],
        "opening_style": [
            "{topic}。",
            "来讲一个正在发生的：{topic}。",
            "大型纪录片之《{关键词}》。{topic}。",
        ],
        "phrases": ["这不讲武德", "数据不会骗人你自己去看", "把东西做好把价格打下来", "说大不大说小不小"],
        "forbidden": ["不抄新闻标题", "不写科普式长文", "不情绪化站队"],
        "tags": "#纪录片 #商业 #社会热点",
        "signature": "你怎么看？评论区聊。",
    },
    "人类观察菌": {
        "identity": "冷静社会观察者，摆事实不讲道理",
        "title_rules": [
            "今日热点信息快报。{话题1} {话题2} {话题3}",
            "一条热乎的新闻：{话题}。",
        ],
        "opening_style": [
            "今日热点信息快报。{topic}。",
            "一条热乎的新闻：{topic}。",
            "今天观察到一个现象：{topic}。",
        ],
        "phrases": ["先说基本事实", "有意思的部分来了", "我不给结论只呈现信息", "大家自行判断"],
        "forbidden": ["不下主观结论", "不带情绪节奏", "不写太长"],
        "tags": "#社会热点信息差 #万万没想到 #逆天",
        "signature": "评论区聊聊你的分析。",
    },
    "沙漠一之雕": {
        "identity": "快节奏新闻播报员，信息量大节奏快",
        "title_rules": [
            "{日期}热点快报 / 今日热点快报",
        ],
        "opening_style": [
            "一夜之间发生了啥？{today}热点快报。第一条——{topic}。",
            "{today}热点开唠。先唠第一个：{topic}。",
        ],
        "phrases": ["下一条——", "目前这件事还在发酵", "起因很简单但后面发生的事完全出乎意料", "来评论区一人一句"],
        "forbidden": ["不废话", "不写长句子", "不堆砌观点"],
        "tags": "#热点快报 #社会热点 #新闻",
        "signature": "来评论区一人一句。",
    },
}

# ═══════════════════════════════════════════════════════
#  基于创作指南生成灵感
# ═══════════════════════════════════════════════════════

def extract_topic_kw(topic, n=15):
    topic = re.sub(r'#\S+', '', topic).strip('，。！？；、:： ')
    if len(topic) <= n:
        return topic
    for sep in '，。！？；、:： ':
        idx = topic.find(sep)
        if 3 <= idx <= n:
            return topic[:idx]
    return topic[:n]

def douyin_score(a):
    import math
    score = 0
    title = a.get("title", "")
    likes = a.get("likes", 0) or 0
    comments = a.get("comments", 0) or 0
    source = a.get("source", "")
    if likes > 0: score += min(35, math.log2(likes + 1) * 2)
    if comments > 0: score += min(25, math.log2(comments + 1) * 1.8)
    for w in ['泪崩','震惊','怒了','崩溃','炸裂','反转','意外','惊人','离谱','逆天','破防','绷不住']:
        if w in title: score += 12; break
    for w in ['回应','道歉','曝光','争议','投诉','维权','实名举报','偷税','造假']:
        if w in title: score += 10; break
    clean = re.sub(r'\[.*?\]|#\S+','', title).strip()
    if len(clean) <= 12: score += 10
    elif len(clean) <= 20: score += 6
    source_boost = {'百度热搜':8,'微博':7,'知乎':6,'bilibili':6,'今日头条':5}
    score += source_boost.get(source, 2)
    return score

def select_topics(data, min_score=30):
    """按爆火潜力筛选，不设上限"""
    articles = [a for a in data.get("articles", []) if a.get("source") != "blogger"]
    seen = set()
    unique = []
    for a in sorted(articles, key=douyin_score, reverse=True):
        t = a.get("title", "")
        if t and t not in seen:
            seen.add(t)
            if douyin_score(a) >= min_score:
                unique.append(a)
    return unique

def generate_for(name, guide, topic, source, seed):
    random.seed(seed)
    today = datetime.now().strftime("%m月%d日")
    kw = extract_topic_kw(topic)
    
    # 随机选开场风格
    opening_tpl = random.choice(guide["opening_style"])
    slogan = random.choice(["今天呢", f"{today}呢"])
    opening = opening_tpl.replace("{today}", today).replace("{slogan}", slogan).replace("{topic}", topic).replace("{关键词}", kw)
    
    # 随机选口头禅
    phrase = random.choice(guide["phrases"]) if guide["phrases"] else ""
    
    # 标签
    tags = guide["tags"]
    
    # 根据博主不同风格生成
    if name == "网吧信息差":
        contents = [
            f"{opening}这事儿一出来，网友们直接绷不住了。{phrase}，有人说这也太离谱了，有人说这背后肯定有故事。评论区聊聊。\n{tags}",
            f"{opening}{phrase}，这操作属实有点迷。说白了，{topic}这事儿，真就大学生日常。\n{tags}",
            f"{opening}{phrase}，我就想问，这合理吗？评论区一人说一个。\n{tags}",
        ]
    elif name == "阿七大型纪录片":
        contents = [
            f"{opening}你只刷一条短视频，很容易忽略这件事的关键节点。不同平台讲的角度完全不一样：有人看到情绪，有人看到逻辑，还有人看到背景。{phrase}。\n{tags}",
            f"{opening}{phrase}，这件事水比表面深。我帮你把几个版本拼在一起，信息差就出来了。\n{tags}",
            f"{opening}这个事儿背后的人群和节点，比标题本身更值得注意。{phrase}。\n{tags}",
        ]
    elif name == "陈先生":
        contents = [
            f"{opening}{phrase}，直接把网友们整不会了。反转来得比预想的快。你怎么看？评论区聊。\n{tags}",
            f"{opening}这件事如果放在三年前没有人会信。{phrase}。不是运气好，是整个行业走到了拐点。\n{tags}",
            f"{opening}{phrase}。数据不会骗人，你自己去看。\n{tags}",
        ]
    elif name == "人类观察菌":
        contents = [
            f"{opening}{phrase}，这件事的细节比标题丰富得多。我整理了一下公开信息，发现几个容易被忽略的点，大家自行判断。\n{tags}",
            f"{opening}先说基本事实——{phrase}。有意思的部分来了：不同来源的说法完全不一样。我不给结论，只呈现信息。\n{tags}",
            f"{opening}{phrase}。如果你只刷短视频，很容易错过这件事最关键的信息。\n{tags}",
        ]
    elif name == "沙漠一之雕":
        contents = [
            f"{opening}{phrase}。起因很简单，但后面发生的事完全出乎意料。后续还在跟进。来评论区一人一句。\n{tags}",
            f"{opening}{phrase}。目前这件事还在发酵，后续值得盯一下。\n{tags}",
            f"{opening}给还没看的朋友用一句话说清楚——{topic}。{phrase}。来评论区一人一句。\n{tags}",
        ]
    else:
        contents = [f"{topic}。你怎么看？"]
    
    return random.choice(contents)

def main():
    print("=== 灵感生成器 v4 ===\n")
    data = load_json(DATA_FILE)
    
    # 按爆火潜力筛选，取评分最高的200条
    topics = select_topics(data, min_score=25)[:200]
    print(f"筛选出 {len(topics)} 个高爆火潜力话题（top200）\n")
    
    inspirations = []
    for a in topics:
        topic = a.get("title", "")
        source = a.get("source", "")
        if not topic:
            continue
        
        insp = {
            "topic": topic,
            "source": source,
            "score": douyin_score(a),
        }
        
        name_map = {
            "网吧信息差": "wangba",
            "阿七大型纪录片": "aqi",
            "陈先生": "chen",
            "人类观察菌": "guancha",
            "沙漠一之雕": "shadi",
        }
        
        for name, key in name_map.items():
            guide = BLOGGER_GUIDE.get(name, {})
            seed = f"{topic}_{name}_{random.randint(1, 99999)}"
            insp[key] = generate_for(name, guide, topic, source, seed)
        
        inspirations.append(insp)
    
    inspirations.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    data["inspirations"] = inspirations
    data["updated_at"] = datetime.now().isoformat()
    save_json(DATA_FILE, data)
    
    print(f"✅ 已生成 {len(inspirations)} 条灵感")
    print(f"   前3: {', '.join([i['topic'][:15] for i in inspirations[:3]])}")

if __name__ == "__main__":
    main()
