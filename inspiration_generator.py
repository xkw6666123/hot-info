#!/usr/bin/env python3
"""
灵感生成器 v7 —— 基于真实事件背景，用博主口吻完整讲述
- 从 summary 提取时间/来历/结果
- 每个博主按自己的开头/中间/结尾模式串起来
- 像真实视频文案一样：有起因经过结果
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

def extract_topic(topic, n=20):
    topic = re.sub(r'#\S+', '', topic).strip('，。！？；、:： ')
    for sep in '，。！？；、:： ':
        idx = topic.find(sep)
        if 3 <= idx <= n:
            return topic[:idx]
    return topic[:n] if len(topic) > n else topic

def clean_summary(text):
    """清洗摘要：去掉HTML标签，截取合适长度"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[\n\r\t]', '', text).strip()
    if len(text) > 300:
        for sep in '。！？':
            idx = text[:300].rfind(sep)
            if idx > 150:
                return text[:idx+1]
        return text[:300]
    return text

def douyin_score(a):
    import math
    score = 0
    title = a.get("title", "")
    likes = a.get("likes", 0) or 0
    source = a.get("source", "")
    if likes > 0: score += min(35, math.log2(likes + 1) * 2)
    for w in ['泪崩','震惊','怒了','崩溃','炸裂','反转','意外','惊人','离谱','逆天','破防','绷不住']:
        if w in title: score += 12; break
    for w in ['回应','道歉','曝光','争议','维权','举报','偷税','造假']:
        if w in title: score += 10; break
    clean = re.sub(r'\[.*?\]|#\S+','', title).strip()
    if len(clean) <= 12: score += 10
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
#  基于事件背景 + 博主口吻 生成完整叙事
# ═══════════════════════════════════════════════════════

def build_context(topic, summary, date, source):
    """从summary建立事件上下文：时间+起因+经过+结果"""
    ctx = {"time": "", "cause": "", "result": "", "full": ""}
    s = clean_summary(summary or "")
    if not s:
        ctx["full"] = topic
        return ctx
    
    d = date or ""
    # 提取时间
    time_match = re.search(r'(\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月\d{1,2}日|近日|目前|今天|昨晚|北京时间\d{1,2}月\d{1,2}日)', s)
    if time_match:
        ctx["time"] = time_match.group(0)
    elif d:
        ctx["time"] = d
    
    ctx["full"] = s
    return ctx

def wangba_write(topic, summary, date, source):
    """网吧信息差：口语化长文案，完整事件叙事"""
    today = datetime.now().strftime("%m月%d日")
    kw = extract_topic(topic)
    ctx = build_context(topic, summary, date, source)
    s = ctx["full"]
    t = ctx["time"] or today
    
    # 开场
    openers = [
        f"那么嘛，先说{today}呢，首先第一个，{topic}。",
        f"说到吧，今天是{today}呢，咱首先第一个事儿，巴沙是真没想到啊，{topic}。",
        f"说回到新闻，{today}呢，首先第一个，{topic}。",
    ]
    random.seed(topic + "_wbo")
    opening = random.choice(openers)
    
    # 中间——讲述事件（用summary填充，去除官方语气）
    if len(s) > 40:
        # 把官方摘要改写为口语化
        story = s.replace("经审理查明", "说是") \
                 .replace("经调查", "说是") \
                 .replace("据报道", "说") \
                 .replace("据悉", "说") \
                 .replace("目前", "截止到现在啊") \
                 .replace("近日", "就这两天")[:250]
        # 加博主评论
        mid_phrases = [
            f"{story}。那听到这儿，各位不用问了啊。这事儿一出来，网友们直接就绷不住了。",
            f"{story}。哎，不过有意思的来了。",
            f"{story}。那我说白了，{kw}这事儿，评论区也吵翻了。",
        ]
    else:
        mid_phrases = [
            f"这事儿一出来，网友们直接就绷不住了。有人说这也太离谱了，有人说这背后肯定有故事。",
            f"那我说白了，{kw}这事儿，真就让人整不会了。",
        ]
    
    random.seed(topic + "_wbm")
    mid = random.choice(mid_phrases)
    
    # 结尾
    closers = [
        "但不管怎么说，这事儿确实挺有意思的。你们遇到过类似的事吗？评论区分享一下。",
        "OK下事儿。各位评论区聊聊，你们怎么看这个事。",
        "这事儿后续巴沙还会跟进的，评论区聊聊你们的看法。",
    ]
    random.seed(topic + "_wbc")
    close = random.choice(closers)
    
    return f"{opening}{mid}。{close}"

def aqi_write(topic, summary, date, source):
    """阿七大型纪录片：信息差视角，完整时间线+各方回应"""
    today = datetime.now().strftime("%m月%d日")
    ctx = build_context(topic, summary, date, source)
    s = ctx["full"]
    t = ctx["time"] or today
    
    if len(s) > 40:
        story = s.replace("经审理查明", "").replace("经调查", "").replace("据报道", "").replace("据悉", "").replace("目前", "截止到现在")[:200]
        return f"{today}社会热点信息差。今天先讲一个其实挺重要但没什么人深聊的事：{topic}。事情是这样的——{story}。你可能觉得这跟你没什么关系，但巴沙帮你理一下：不同平台在讲这件事的时候，侧重点完全不一样。微博在强调情绪，知乎在分析逻辑，评论区的大哥在科普背景。每个版本都只说了一半的事实。另一半在哪里？就在信息差里。OK下一件事。"
    else:
        return f"热点信息差，{topic}。这事儿一出来，很多朋友可能只是看了一眼标题就划走了。但巴沙注意到一个细节：不同平台讲的角度完全不一样。有人看到情绪，有人看到逻辑，还有人看到背景。巴沙花了半天把这些版本都看了一遍，发现每个版本都只说了一半的事实。OK下一件事。"

def chen_write(topic, summary, date, source):
    """陈先生：纪录片旁白，事件+反转"""
    kw = extract_topic(topic)
    ctx = build_context(topic, summary, date, source)
    s = ctx["full"]
    t = ctx["time"] or ""
    
    if len(s) > 40:
        story = s[:150]
        return f"大型纪录片之《{kw}》。{story}。讲真的，这个事发生的时候我一点都不意外。在过去几个月里，类似的事情已经不是第一次了。大家觉得这是小概率事件，其实完全不是——只是以前没人统计罢了。现在统计出来了，数字摆在那里。你怎么看？"
    else:
        return f"大型纪录片之《{kw}》持续为您播出。{topic}，这件事如果放在三年前没有人会信。但现在它真实地发生了。你怎么看？"

def guancha_write(topic, summary, date, source):
    """人类观察菌：客观呈现，公开信息整理"""
    kw = extract_topic(topic)
    ctx = build_context(topic, summary, date, source)
    s = ctx["full"]
    t = ctx["time"] or ""
    
    if len(s) > 40:
        story = s[:200]
        return f"今日热点信息快报。先说基本事实——{story}。然后有意思的部分来了：官方说——当事人说——网友说——三个版本，三个世界。我不告诉你谁对谁错，把所有能找到的公开信息放在下面，你自己比对，自己判断。评论区聊聊你的分析。"
    else:
        return f"今日热点信息快报。{topic}。我整理了一下公开信息的时间线。今天我不给结论，只呈现信息，结论交给你。评论区聊聊。"

def shadi_write(topic, summary, date, source):
    """沙漠一之雕：快节奏，一个接一个讲"""
    today = datetime.now().strftime("%m月%d日")
    kw = extract_topic(topic)
    ctx = build_context(topic, summary, date, source)
    s = ctx["full"]
    
    if len(s) > 40:
        story = s[:180]
        return f"一夜之间发生了啥？{today}热点快报。第一条——{topic}。{story}。目前这件事还在发酵，后续值得盯一下。来评论区一人一句。"
    else:
        return f"{today}热点开唠。先唠第一个：{topic}。起因很简单，但后面发生的事完全出乎意料。后续还在跟进。来评论区一人一句。"

def main():
    print("=== 灵感生成器 v7（基于事件背景+博主口吻） ===\n")
    data = load_json(DATA_FILE)
    topics = select_topics(data, n=200)
    print(f"筛选 {len(topics)} 个高爆火话题\n")
    
    writers = {
        "wangba": wangba_write, "aqi": aqi_write,
        "chen": chen_write, "guancha": guancha_write, "shadi": shadi_write,
    }
    
    inspirations = []
    for a in topics:
        topic = a.get("title", "")
        source = a.get("source", "")
        summary = a.get("summary", "")
        date = a.get("date", "")
        if not topic:
            continue
        insp = {"topic": topic, "source": source, "score": douyin_score(a), "date": date}
        for key, writer in writers.items():
            insp[key] = writer(topic, summary, date, source)
        inspirations.append(insp)
    
    inspirations.sort(key=lambda x: x.get("score", 0), reverse=True)
    data["inspirations"] = inspirations
    data["updated_at"] = datetime.now().isoformat()
    save_json(DATA_FILE, data)
    
    print(f"✅ 已生成 {len(inspirations)} 条灵感")
    for i in range(3):
        insp = inspirations[i]
        print(f"  {i+1}. [{insp['score']:.0f}分] {insp['topic'][:25]}")
        wb = insp['wangba'][:100]
        print(f"     → {wb}...")

if __name__ == "__main__":
    main()
