#!/usr/bin/env python3
"""
灵感生成器 v9 —— 用博主口吻完整转述新闻
核心理念：把每篇热搜新闻用5位博主的风格分别重写一遍
就像他们真的在视频里讲了这条新闻
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

def clean_text(s):
    s = re.sub(r'<[^>]+>', '', s or "")
    s = re.sub(r'[\n\r\t]', ' ', s).strip()
    return s[:500]  # 取前500字

def douyin_score(a):
    import math; score = 0
    t = a.get("title",""); likes = a.get("likes",0) or 0
    if likes>0: score += min(35, math.log2(likes+1)*2)
    for w in ['泪崩','震惊','怒了','崩溃','炸裂','反转','意外','惊人','离谱','逆天','破防','绷不住']:
        if w in t: score += 12; break
    for w in ['回应','道歉','曝光','争议','维权','举报','偷税','造假']:
        if w in t: score += 10; break
    clean = re.sub(r'\[.*?\]|#\S+','',t).strip()
    if len(clean)<=12: score+=10
    boost={'百度热搜':8,'微博':7,'知乎':6,'bilibili':6,'今日头条':5}
    score+=boost.get(a.get("source",""),2)
    return score

def select_topics(data, n=200):
    arts = [a for a in data.get("articles",[]) if a.get("source")!="blogger"]
    seen = set(); uni = []
    for a in sorted(arts, key=douyin_score, reverse=True):
        t = a.get("title","")
        if t and t not in seen and douyin_score(a)>=25:
            seen.add(t); uni.append(a)
    return uni[:n]

# ═══════════════════════════════════════════════════════
#  每位博主 = 一台"新闻翻译机"
#  把官方摘要转成博主自己的语言
# ═══════════════════════════════════════════════════════

def wangba_translate(topic, summary):
    """网吧信息差：把新闻翻译成大学生吐槽"""
    today = datetime.now().strftime("%m月%d日")
    s = clean_text(summary)
    
    opens = [
        f"那么嘛，先说{today}呢，首先第一个，巴沙是真没想到啊，{topic}。",
        f"说到吧，今天是{today}呢，咱首先第一个事儿，{topic}。",
        f"说回到新闻，{today}呢，首先第一个，{topic}。",
    ]
    random.seed(topic+"wbo"); opening = random.choice(opens)
    
    # 把官方摘要翻译成口语
    if s and len(s)>20:
        story = s.replace("经审理查明：","简单来说就是，") \
                 .replace("经调查","据了解") \
                 .replace("据报道","说是啊") \
                 .replace("据悉","听说啊") \
                 .replace("目前","截止到现在啊") \
                 .replace("近日","就这两天") \
                 .replace("北京时间","") \
                 .replace("中共中央总书记、国家主席、中央军委主席","") \
                 .replace("人民法院","法院") \
                 .replace("人民检察院","检察院") \
                 .replace("被告人","这哥们") \
                 .replace("非法收受财物","贪了") \
                 .replace("判处死刑","直接判了死刑") \
                 .replace("一审公开宣判","审完直接判了") \
                 .replace("应急响应","紧急预警") \
                 .replace("部署开展","开始搞") \
                 .replace("进一步研究部署","继续研究")[:350]
    else:
        story = f"这事儿说来话长了。{topic}——"
    
    mids = [
        f"{story}。那听到这儿，各位不用问了啊。网友们直接就绷不住了。",
        f"{story}。那我说白了，这事儿评论区也吵翻了。",
        f"{story}。哎，不过有意思的来了。",
    ]
    random.seed(topic+"wbm"); mid = random.choice(mids)
    
    ends = [
        "你们遇到过类似的事吗？评论区分享一下。",
        "OK下事儿。评论区聊聊你们怎么看。",
        "这事儿后续巴沙还会跟进的。评论区聊聊。",
    ]
    random.seed(topic+"wbe"); end = random.choice(ends)
    
    return f"{opening}{mid}。{end}"

def aqi_translate(topic, summary):
    """阿七纪录片：信息差深度解读"""
    today = datetime.now().strftime("%m月%d日")
    s = clean_text(summary) if summary else topic
    
    if s and len(s)>20:
        story = s.replace("经审理查明","")[:300]
        return f"{today}社会热点信息差。今天讲一件其实挺重要但没什么人深聊的事：{topic}。事情是这样的——{story}。你可能觉得这跟你没什么关系，但巴沙帮你理一下：不同平台讲同一个话题的时候，侧重点完全不一样。微博在强调情绪，知乎在分析逻辑，每个版本都只说了一半的事实。另一半在哪？就在信息差里。OK下一件事。"
    else:
        return f"热点信息差，{topic}。巴沙花了半天把各平台版本都看了一遍，发现每个版本都只说了一半的事实。信息差就在细节里。OK下一件事。"

def chen_translate(topic, summary):
    """陈先生：纪录片旁白"""
    s = clean_text(summary) if summary else topic
    kw = topic[:20]
    
    if s and len(s)>20:
        story = s[:250]
        return f"大型纪录片之《{kw}》持续为您播出。{story}。讲真的，这个事发生的时候我一点都不意外。在过去几个月里，类似的事情已经不是第一次了。大家觉得是小概率事件——完全不是。只是以前没人统计。现在统计出来了，数字摆在那里。你怎么看？"
    else:
        return f"大型纪录片之《{kw}》持续为您播出。{topic}。这件事如果放在三年前没有人会信，但现在它真实地发生了。你怎么看？"

def guancha_translate(topic, summary):
    """人类观察菌：客观整理"""
    s = clean_text(summary) if summary else topic
    
    if s and len(s)>20:
        story = s[:250]
        return f"今日热点信息快报。先说基本事实——{story}。有意思的部分来了：不同来源的说法完全不一样。官方的、当事人的、网友的——三个版本，三个世界。我不告诉你谁对谁错，我把能找到的公开信息放在下面，你自己比对判断。评论区聊聊你的分析。"
    else:
        return f"今日热点信息快报。{topic}。我不给结论，只呈现信息。评论区聊聊你的视角。"

def shadi_translate(topic, summary):
    """沙漠一之雕：快节奏"""
    today = datetime.now().strftime("%m月%d日")
    s = clean_text(summary) if summary else topic
    
    if s and len(s)>20:
        story = s[:200]
        return f"一夜之间发生了啥？{today}热点快报。第一条——{topic}。{story}。目前这件事还在发酵，后续值得盯一下。来评论区一人一句。"
    else:
        return f"{today}热点开唠。先唠第一个：{topic}。起因很简单，但后面的事完全出乎意料。后续还在跟进。来评论区一人一句。"

def main():
    print("=== 灵感生成器 v9 博主风格新闻翻译机 ===\n")
    data = load_json(DATA_FILE)
    topics = select_topics(data, n=200)
    print(f"筛选 {len(topics)} 个高爆火话题\n")
    
    translators = {
        "wangba": wangba_translate, "aqi": aqi_translate,
        "chen": chen_translate, "guancha": guancha_translate, "shadi": shadi_translate,
    }
    
    inspirations = []
    for a in topics:
        topic = a.get("title","")
        summary = a.get("summary","")
        if not topic: continue
        insp = {"topic": topic, "source": a.get("source",""), "score": douyin_score(a)}
        for key, translator in translators.items():
            insp[key] = translator(topic, summary)
        inspirations.append(insp)
    
    inspirations.sort(key=lambda x: x.get("score",0), reverse=True)
    data["inspirations"] = inspirations
    data["updated_at"] = datetime.now().isoformat()
    save_json(DATA_FILE, data)
    
    # 展示样例
    print(f"✅ {len(inspirations)} 条")
    ins = inspirations[0]
    print(f"【{ins['score']:.0f}分】{ins['topic']}")
    print(f"\n网吧信息差：{ins['wangba'][:200]}")
    print(f"\n阿七：{ins['aqi'][:200]}")
    print(f"\n陈先生：{ins['chen'][:200]}")

if __name__ == "__main__":
    main()
