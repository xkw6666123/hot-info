#!/usr/bin/env python3
"""
灵感生成器 v6 —— 基于 archive 真实文案口吻生成
每位博主独立风格，像本人讲这个热点话题一样写
网吧信息差：长篇口语串联，不是标题
"""
import json, os, re, random
from datetime import datetime
from collections import defaultdict

WORK = r"D:\AI\hotinfo\hot-info"
DATA_FILE = os.path.join(WORK, "data.json")

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_json(path, data):
    base = os.path.basename(path)
    tmp = os.path.join(os.getcwd(), base + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def extract_topic(topic, n=15):
    topic = re.sub(r'#\S+', '', topic).strip('，。！？；、:： ')
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
    for w in ['回应','道歉','曝光','争议','投诉','维权','举报','偷税','造假']:
        if w in title: score += 10; break
    clean = re.sub(r'\[.*?\]|#\S+','', title).strip()
    if len(clean) <= 12: score += 10
    elif len(clean) <= 20: score += 6
    source_boost = {'百度热搜':8,'微博':7,'知乎':6,'bilibili':6,'今日头条':5}
    score += source_boost.get(source, 2)
    return score

def select_topics(data, n=200):
    articles = [a for a in data.get("articles", []) if a.get("source") != "blogger"]
    seen = set()
    unique = []
    for a in sorted(articles, key=douyin_score, reverse=True):
        t = a.get("title", "")
        if t and t not in seen and douyin_score(a) >= 25:
            seen.add(t)
            unique.append(a)
    return unique[:n]

# ═══════════════════════════════════════════════════════
#  基于真实文案的博主风格模板
# ═══════════════════════════════════════════════════════

def wangba_write(topic, source):
    """网吧信息差口吻：长文案，口语化，多段串联，有梗"""
    today = datetime.now().strftime("%m月%d日")
    kw = extract_topic(topic)
    
    openers = [
        f"说到吧，今天是{today}呢，咱首先第一个事儿，巴沙是真没想到啊，{topic}。",
        f"那么嘛，先说{today}呢，首先第一个，{topic}。",
        f"说回到新闻，{today}呢，首先第一个，{topic}。",
    ]
    random.seed(topic + "_wb_o")
    opening = random.choice(openers)
    
    # 展开段落：网吧信息差通常在这个位置会加个人评论/梗
    mid_phrases = [
        f"这事儿一出来，网友们直接就绷不住了。",
        f"那听到这儿，各位不用问了啊，巴沙也想问的。",
        f"哎，不过有意思的来了，{kw}这件事居然——",
        f"那我说白了，{kw}这事儿，真就让人整不会了。",
        f"欧亚这，这事儿巴沙真都懒得喷。",
    ]
    random.seed(topic + "_wb_m")
    mid = random.choice(mid_phrases)
    
    # 评论互动
    comments = [
        f"有人说这也太离谱了，有人说这背后肯定有故事，还有人说这完全就是剧本。",
        f"评论区也吵翻了，有人说这操作属实逆天，有人说这不是第一次了。",
        f"说白了，{kw}这事儿，就是典型的——你从标题看不出水有多深的那种。",
    ]
    random.seed(topic + "_wb_c")
    comment = random.choice(comments)
    
    closers = [
        f"但不管怎么说，这事儿确实挺有意思的。你们遇到过类似的事吗？评论区分享一下。",
        f"OK下事儿。各位评论区聊聊，你们怎么看这个事。",
        f"这事儿后续巴沙还会跟进的，评论区聊聊你们的看法。",
    ]
    random.seed(topic + "_wb_cc")
    close = random.choice(closers)
    
    return f"{opening}{mid}{comment}。{close}"

def aqi_write(topic, source):
    """阿七大型纪录片口吻：信息差，逐条分析"""
    kw = extract_topic(topic)
    today = datetime.now().strftime("%m月%d日")
    
    templates = [
        f"热点信息差，{topic}。这事儿一出来，很多朋友可能只是看了一眼标题就划走了。但巴沙注意到一个细节：不同平台在讲这件事的时候，侧重点完全不一样。微博在强调情绪，知乎在分析逻辑，评论区的大哥在科普背景。巴沙花了半天把这些版本都看了一遍，发现每个版本都只说了一半的事实。另一半在哪里？就在你没看到的信息差里。OK下一件事。",
        f"{today}社会热点信息差。今天先讲一个其实挺重要但没什么人深聊的事：{topic}。这类新闻有一个共同特点——标题很平淡，点进去才发现水很深。我分三个角度帮你看：时间线、各方立场、潜在影响。第一个角度——这件事的时间线其实比报道里说的要早将近一周；第二个角度——各方的回应方式本身就很有意思；第三个——这件事背后涉及的人群比表面上多得多。这就是信息差，你看的是新闻，别人看的是信号。",
        f"热点信息差，{topic}。为什么大部分人对这件事的理解是错的？因为信息在传播的过程中，每转一次手就变一次意思，到了热搜上的时候已经面目全非了。巴沙翻了一上午原始资料，发现最早的消息源其实不是你们看到的那个账号，而是一个几乎没人关注的小号。这个传播过程本身就是一个经典的信息差案例。OK下一件事。",
    ]
    random.seed(topic + "_aq")
    return random.choice(templates)

def chen_write(topic, source):
    """陈先生口吻：纪录片旁白，反转幽默"""
    kw = extract_topic(topic)  
    
    is_biz = any(w in topic for w in ['上市','降价','新品','发布','收购','手机','车','股','芯片','AI','裁员','融资','世界杯','比赛'])
    
    if is_biz:
        templates = [
            f"大型纪录片之《{kw}》持续为您播出。{topic}，这件事如果放在三年前，没有人会信。但现在它真实地发生了。不是因为运气好，是因为整个行业走到了一个拐点。以前大家想的是怎么做大，现在所有人都在想怎么活下去。活下去的办法就一条——把东西做好，把价格打下来。不玩虚的。",
            f"这波真的不讲武德。{topic}。过去大家挤在一条赛道上卷，卷到最后谁都赚不到钱。现在有人换了一条路——不是更好，是更对。数据不会骗人，你自己去看。",
        ]
    else:
        templates = [
            f"大型纪录片之《{kw}》。{topic}，讲真的，这个事发生的时候我一点都不意外。因为在过去的三个月里，类似的事情已经有四五起了。大家觉得这是小概率事件，其实完全不是——只是以前没人统计罢了。现在统计出来了，数字摆在那里，不信也得信。",
            f"今天讲一个现象级的新闻：{topic}。我翻了一下评论区，点赞最高的三条评论分别代表了三种完全不同的立场。有意思的不是他们说了什么，而是他们的点赞数——这场争论其实没有赢家。",
        ]
    random.seed(topic + "_ch")
    return random.choice(templates)

def guancha_write(topic, source):
    """人类观察菌口吻：冷静观察，摆事实"""
    kw = extract_topic(topic)
    
    templates = [
        f"今日热点信息快报。{topic}。先说基本事实——这是目前可以确认的信息。然后有意思的部分来了：官方说的是A，当事人说的是B，网友说的是C。三个版本，三个世界。我不告诉你谁对谁错，我把所有能找到的公开信息放在下面，你自己比对，自己判断。评论区聊聊你的分析。",
        f"一条热乎的新闻：{topic}。我整理了一下公开信息的时间线——最开始是——然后是——转折出现在——现在的状态是——。你看完这条时间线，有没有觉得哪里不对劲？评论区告诉我你注意到的是什么。",
        f"热点快报，先看数据：{topic}。我注意到三个细节，其他报道基本都只提了第一个。细节一——细节二——细节三——。这三个细节连起来，指向一个不太一样的方向。今天我不给结论，只呈现信息。",
    ]
    random.seed(topic + "_gc")
    return random.choice(templates)

def shadi_write(topic, source):
    """沙漠一之雕口吻：快节奏连播"""
    kw = extract_topic(topic)
    today = datetime.now().strftime("%m月%d日")
    
    templates = [
        f"一夜之间发生了啥？{today}热点快报。第一条——{topic}。起因很简单，但后面发生的事完全出乎意料。大家现在最关心的问题是——后续会怎么发展？来评论区一人一句。",
        f"{today}热点开唠。先唠第一个：{topic}。给还没看的朋友用一句话说清楚——这件事的来龙去脉。如果你觉得这就是一个简单的A导致B，那可能要重新想想了。来评论区一人一句。",
        f"用两分钟给你补完今天的热搜，先说最火的一个：{topic}。目前我看到的最新情况是这样——后续还在跟进。为什么之前没人关注？因为信息太碎，没人拼起来。今天帮你拼好了。来评论区一人一句。",
    ]
    random.seed(topic + "_sd")
    return random.choice(templates)

def main():
    print("=== 灵感生成器 v6（基于真实文案口吻）===\n")
    data = load_json(DATA_FILE)
    topics = select_topics(data, n=200)
    print(f"筛选 {len(topics)} 个高爆火话题\n")
    
    writers = {
        "wangba": wangba_write,
        "aqi": aqi_write,
        "chen": chen_write,
        "guancha": guancha_write,
        "shadi": shadi_write,
    }
    
    inspirations = []
    for a in topics:
        topic = a.get("title", "")
        source = a.get("source", "")
        if not topic:
            continue
        insp = {"topic": topic, "source": source, "score": douyin_score(a)}
        for key, writer in writers.items():
            insp[key] = writer(topic, source)
        inspirations.append(insp)
    
    inspirations.sort(key=lambda x: x.get("score", 0), reverse=True)
    data["inspirations"] = inspirations
    data["updated_at"] = datetime.now().isoformat()
    save_json(DATA_FILE, data)
    
    print(f"✅ 已生成 {len(inspirations)} 条灵感")
    for i in range(3):
        insp = inspirations[i]
        print(f"  {i+1}. [{insp['score']:.0f}分] {insp['topic'][:20]}")

if __name__ == "__main__":
    main()
