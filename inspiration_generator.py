#!/usr/bin/env python3
"""
灵感生成器 v8 —— 结构化叙事模板
从summary提取 时间/起因/结果，填入博主专属叙事结构
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
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[\n\r\t]', ' ', text).strip()
    # 拆句，只取前2句
    sents = re.split(r'[。！？]', text)
    result = ""
    for s in sents[:3]:
        s = s.strip()
        if len(s) > 10:
            result += s + "。"
    return result[:300]

def parse_event(summary, date):
    """从summary中提取 时间/起因/结果"""
    info = {"time": date or "", "what": "", "result": ""}
    s = clean_summary(summary or "")
    if not s:
        return info
    
    # 提取时间
    tm = re.search(r'(\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月\d{1,2}日|近日|目前)', s)
    if tm:
        info["time"] = tm.group(0)
    
    # 分成两半：起因 + 结果
    sents = re.split(r'[。]', s)
    sents = [x.strip() for x in sents if len(x.strip()) > 10]
    if len(sents) >= 2:
        info["what"] = sents[0]
        info["result"] = sents[1] if len(sents) >= 2 else ""
    else:
        info["what"] = s
    
    return info

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
    boost = {'百度热搜':8,'微博':7,'知乎':6,'bilibili':6,'今日头条':5}
    score += boost.get(source, 2)
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
#  博主专属叙事模板（结构化：时间+起因+经过+结果+互动）
# ═══════════════════════════════════════════════════════

def wangba_write(topic, info):
    """网吧信息差：口语叙事，三段式"""
    today = datetime.now().strftime("%m月%d日")
    kw = extract_topic(topic)
    what = info["what"] or topic
    result = info["result"] or ""
    dt = info["time"] or "最近"
    
    opens = [
        f"那么嘛，先说{today}呢，首先第一个，巴沙是真没想到啊，{topic}。",
        f"说到吧，今天是{today}呢，咱首先第一个事儿，{topic}。",
        f"说回到新闻，{today}呢，首先第一个，{topic}。",
    ]
    random.seed(topic + "wb")
    o = random.choice(opens)
    
    # 事件描述（口语化改写）
    story = what.replace("经审理查明", "简单来说就是").replace("经调查", "据了解").replace("据报道", "").replace("据悉", "").replace("目前", "截止到现在啊")
    
    # 博主评论 + 结果
    comments = [
        f"那听到这儿，各位不用问了啊。{result}。网友们直接就绷不住了，有人说这也太离谱了，有人说这背后肯定有故事。",
        f"那我说白了，{kw}这事儿，{result}。评论区也吵翻了，有人说是剧本，有人说是真的。",
        f"哎，不过有意思的来了。{result}。说白了，这事儿就是典型的你从标题看不出水有多深的那种。",
    ]
    if not result:
        comments = [
            f"那听到这儿，各位不用问了啊。网友们直接就绷不住了。",
            f"那我说白了，这事儿真就让人整不会了。",
            f"欧亚这，这事儿巴沙真都懒得喷。评论区也吵翻了。",
        ]
    random.seed(topic + "wbc")
    c = random.choice(comments)
    
    closes = [
        "你们遇到过类似的事吗？评论区分享一下。",
        "OK下事儿。评论区聊聊你们怎么看。",
        "这事儿后续巴沙还会跟进的。评论区聊聊。",
    ]
    random.seed(topic + "wbe")
    cl = random.choice(closes)
    
    return f"{o}{story}。{c}。{cl}"

def aqi_write(topic, info):
    """阿七纪录片：信息差深度分析"""
    today = datetime.now().strftime("%m月%d日")
    what = info["what"] or topic
    result = info["result"] or ""
    
    return f"{today}社会热点信息差。今天先讲一件其实挺重要但没什么人深聊的事：{topic}。事情是这样的——{what}。{result}。你可能觉得这跟你没什么关系，但巴沙帮你理一下：不同平台在讲这件事的时候，侧重点完全不一样。微博在强调情绪，知乎在分析逻辑，每个版本都只说了一半的事实。另一半在哪里？就在你没看到的信息差里。OK下一件事。"

def chen_write(topic, info):
    """陈先生：纪录片旁白体"""
    kw = extract_topic(topic)
    what = info["what"] or topic
    result = info["result"] or ""
    
    if result:
        return f"大型纪录片之《{kw}》持续为您播出。{what}。{result}。讲真的，这个事发生的时候我一点都不意外。在过去几个月里，类似的事情已经不是第一次了。大家觉得是小概率事件，其实完全不是——只是以前没人统计罢了。现在统计出来了，数字摆在那里，不信也得信。"
    else:
        return f"今天讲一个现象级的新闻：{topic}。{what}。有意思的不是事件本身，而是各方的反应。甲方说——乙方说——网友说——。这场争论其实没有赢家。"

def guancha_write(topic, info):
    """人类观察菌：客观整理"""
    what = info["what"] or topic
    result = info["result"] or ""
    
    if result:
        return f"今日热点信息快报。先说基本事实——{what}。{result}。然后有意思的部分来了：不同来源的说法完全不一样。我不告诉你谁对谁错，把所有能找到的公开信息放在下面，你自己比对，自己判断。评论区聊聊你的分析。"
    else:
        return f"今日热点信息快报。{topic}。{what}。我整理了一下公开信息的时间线，发现几个容易被忽略的细节。今天我不给结论，只呈现信息，评论区聊聊你的视角。"

def shadi_write(topic, info):
    """沙漠一之雕：快节奏连播"""
    today = datetime.now().strftime("%m月%d日")
    what = info["what"] or topic
    result = info["result"] or ""
    
    if result:
        return f"一夜之间发生了啥？{today}热点快报。第一条——{topic}。{what}。{result}。目前这件事还在发酵，后续值得盯一下。来评论区一人一句。"
    else:
        return f"{today}热点开唠。先唠第一个：{topic}。{what}。起因很简单，但后面发生的事完全出乎意料。后续还在跟进。来评论区一人一句。"

def main():
    print("=== 灵感生成器 v8 结构化叙事 ===\n")
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
        if not topic: continue
        info = parse_event(summary, date)
        insp = {"topic": topic, "source": source, "score": douyin_score(a)}
        for key, writer in writers.items():
            insp[key] = writer(topic, info)
        inspirations.append(insp)
    
    inspirations.sort(key=lambda x: x.get("score", 0), reverse=True)
    data["inspirations"] = inspirations
    data["updated_at"] = datetime.now().isoformat()
    save_json(DATA_FILE, data)
    
    print(f"✅ 已生成 {len(inspirations)} 条灵感")
    for i in range(3):
        ins = inspirations[i]
        print(f"  {i+1}. [{ins['score']:.0f}分] {ins['topic'][:25]}")
        print(f"     🗣 {ins['wangba'][:120]}")
        print()

if __name__ == "__main__":
    main()
