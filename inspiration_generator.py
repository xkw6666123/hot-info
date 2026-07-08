#!/usr/bin/env python3
"""
灵感生成器 v10 —— 🧠 持续学习 + 新闻完整转述
- 从 deep_style_learned.json 加载持续学到的风格词（情感词/转折词）
- 随着博主文案积累，学到的词越来越准确，灵感越来越像
- 完整叙事：起因→经过→结果
"""
import json, os, re, random
from datetime import datetime, timezone

WORK = r"D:\AI\hotinfo\hot-info"
DATA_FILE = os.path.join(WORK, "data.json")
STYLE_FILE = os.path.join(WORK, "deep_style_learned.json")

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_json(path, data):
    base = os.path.basename(path)
    tmp = os.path.join(os.getcwd(), base + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def pick(items, seed):
    if not items: return ""
    random.seed(seed)
    return random.choice(items)

def clean_text(s):
    s = re.sub(r'<[^>]+>', '', s or "")
    s = re.sub(r'[\n\r\t]', ' ', s).strip()
    return s[:400]

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

def parse_event(summary):
    """把summary拆成起因+经过+结果"""
    s = clean_text(summary or "")
    if not s: return {"cause":"", "detail":"", "result":""}
    sents = [x.strip() for x in re.split(r'[。；]', s) if len(x.strip())>10]
    return {
        "cause": sents[0] if len(sents)>=1 else s,
        "detail": sents[1] if len(sents)>=2 else "",
        "result": sents[2] if len(sents)>=3 else (sents[1] if len(sents)>=2 else ""),
    }

# ═══════════════════════════════════════════════════════
#  基于持续学习风格词 + 完整叙事结构 生成
# ═══════════════════════════════════════════════════════

def wangba_write(topic, event, style):
    """网吧信息差：起因→经过→结果 + 评论 + 互动"""
    today = datetime.now().strftime("%m月%d日")
    emotion = pick(style.get("emotions",["离谱"]), topic+"_emo")
    trans = pick(style.get("connectors",["不过"]), topic+"_trans")
    
    opens = [
        f"那么嘛，先说{today}呢，首先第一个，巴沙是真没想到啊，{topic}。",
        f"说到吧，今天是{today}呢，咱首先第一个事儿，{topic}。",
        f"说回到新闻，{today}呢，首先第一个，{topic}。",
    ]
    opening = pick(opens, topic+"_open")
    
    # 起因→经过→结果 结构
    cause = event.get("cause","") or topic
    detail = event.get("detail","")
    result = event.get("result","")
    
    # 口语化改写
    for old, new in [("经审理查明：","简单来说就是，"),("经调查","据了解"),
                      ("据报道","说是啊"),("据悉","听说啊"),("目前","截止到现在啊"),
                      ("近日","就这两天"),("人民法院","法院"),("被告人","这哥们"),
                      ("非法收受财物","贪了"),("判处死刑","直接判了死刑")]:
        cause = cause.replace(old, new)
    
    # 起因叙述
    story = f"起因是这样——{cause}。"
    if detail:
        story += f"{detail}。"
    if result:
        story += f"结果呢——{result}。"
    
    # 博主评论
    comments = [
        f"{story}那听到这儿，各位不用问了啊。网友们直接就绷不住了，有人说这也太{emotion}了，有人说这背后肯定有故事。",
        f"{story}{trans}，那我说白了，这事儿评论区也吵翻了。有人觉得这太{emotion}了，有人说这完全就是剧本。",
        f"{story}哎，{trans}有意思的来了。说白了，这事儿就是典型的——你从标题看不出水有多深的那种。",
    ]
    comment = pick(comments, topic+"_mid")
    
    ends = [
        "你们遇到过类似的事吗？评论区分享一下。",
        "OK下事儿。评论区聊聊你们怎么看。",
        "这事儿后续巴沙还会跟进的。评论区聊聊。",
    ]
    end = pick(ends, topic+"_end")
    
    return f"{opening}{comment}。{end}"

def aqi_write(topic, event, style):
    """阿七纪录片：起因+各方反应+信息差"""
    today = datetime.now().strftime("%m月%d日")
    trans = pick(style.get("connectors",["不过"]), topic+"_trans")
    cause = event.get("cause","") or topic
    detail = event.get("detail","")
    result = event.get("result","")
    
    story = f"事情是这样的——{cause}。"
    if detail: story += f"{detail}。"
    if result: story += f"后续——{result}。"
    
    return f"{today}社会热点信息差。今天讲一件其实挺重要但没什么人深聊的事：{topic}。{story}{trans}，你可能觉得这跟你没什么关系，但巴沙帮你理一下：不同平台讲同一个话题的时候，侧重点完全不一样。微博在强调情绪，知乎在分析逻辑，每个版本都只说了一半的事实。另一半在哪？就在信息差里。OK下一件事。"

def chen_write(topic, event, style):
    """陈先生：事件+数据+反转"""
    cause = event.get("cause","") or topic
    result = event.get("result","")
    trans = pick(style.get("connectors",["不过"]), topic+"_trans")
    kw = topic[:20]
    
    story = f"{cause}。"
    if result: story += f"{result}。"
    
    return f"大型纪录片之《{kw}》持续为您播出。{story}讲真的，{trans}，这个事发生的时候我一点都不意外。在过去几个月里，类似的事情已经不是第一次了。大家觉得是小概率事件——完全不是。只是以前没人统计。现在统计出来了，数字摆在那里。你怎么看？"

def guancha_write(topic, event, style):
    """人类观察菌：客观事实+多版本"""
    cause = event.get("cause","") or topic
    result = event.get("result","")
    
    story = f"先说基本事实——{cause}。"
    if result: story += f"{result}。"
    
    return f"今日热点信息快报。{story}有意思的部分来了：不同来源的说法完全不一样。官方的、当事人的、网友的——三个版本，三个世界。我不告诉你谁对谁错，我把能找到的公开信息放在下面，你自己比对判断。评论区聊聊你的分析。"

def shadi_write(topic, event, style):
    """沙漠一之雕：快节奏播报"""
    today = datetime.now().strftime("%m月%d日")
    cause = event.get("cause","") or topic
    result = event.get("result","")
    
    story = f"{cause}。"
    if result: story += f"{result}。"
    
    return f"一夜之间发生了啥？{today}热点快报。第一条——{topic}。{story}目前这件事还在发酵，后续值得盯一下。来评论区一人一句。"

def main():
    print("=== 灵感生成器 v10 持续学习+完整叙事 ===\n")
    
    # 加载持续学到的风格词
    learned = {}
    if os.path.exists(STYLE_FILE):
        raw = load_json(STYLE_FILE)
        total = 0
        for name in raw:
            vocab = raw[name].get("vocabulary", {})
            emotions = vocab.get("emotions", [])
            transitions = vocab.get("transitions", [])
            learned[name] = {"emotions": emotions, "connectors": transitions}
            total += len(emotions) + len(transitions)
        print(f"📚 已加载风格词: {total}个（持续学习中）")
        for name in learned:
            e = learned[name].get("emotions",[])
            c = learned[name].get("connectors",[])
            print(f"  {name}: 情感词{e[:4]} 转折词{c[:4]}")
    else:
        print("⚠️ 未找到风格学习数据，使用默认词")
    
    # 默认风格词（兜底）
    defaults = {
        "网吧信息差": {"emotions":["离谱","有意思"], "connectors":["不过","但是","说白了"]},
        "阿七大型纪录片": {"emotions":["离谱","牛"], "connectors":["不过","但是"]},
        "陈先生": {"emotions":["绷不住","绝了"], "connectors":["但是","不过"]},
        "人类观察菌": {"emotions":["逆天","离谱"], "connectors":["不过","其实"]},
        "沙漠一之雕": {"emotions":["离谱","破防"], "connectors":["不过","但是"]},
    }
    
    name_map = {"网吧信息差":"wangba","阿七大型纪录片":"aqi","陈先生":"chen",
                "人类观察菌":"guancha","沙漠一之雕":"shadi"}
    
    data = load_json(DATA_FILE)
    topics = select_topics(data, n=200)
    print(f"\n筛选 {len(topics)} 个高爆火话题\n")
    
    writers = {"wangba": wangba_write, "aqi": aqi_write, "chen": chen_write,
               "guancha": guancha_write, "shadi": shadi_write}
    
    inspirations = []
    for a in topics:
        topic = a.get("title","")
        summary = a.get("summary","")
        if not topic: continue
        
        event = parse_event(summary)
        insp = {"topic": topic, "source": a.get("source",""), "score": douyin_score(a)}
        
        for cn_name, key in name_map.items():
            style = learned.get(cn_name, defaults.get(cn_name, {"emotions":[],"connectors":[]}))
            insp[key] = writers[key](topic, event, style)
        
        inspirations.append(insp)
    
    inspirations.sort(key=lambda x: x.get("score",0), reverse=True)
    data["inspirations"] = inspirations
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    save_json(DATA_FILE, data)
    
    print(f"✅ {len(inspirations)} 条")
    ins = inspirations[0]
    print(f"【{ins['score']:.0f}分】{ins['topic']}")
    print(f"\n网吧信息差：{ins['wangba'][:200]}")
    print(f"\n阿七：{ins['aqi'][:200]}")

if __name__ == "__main__":
    main()
