#!/usr/bin/env python3
"""
灵感生成器 v10 —— 🧠 持续学习 + 新闻完整转述
- 从 deep_style_learned.json 加载持续学到的风格词（情感词/转折词）
- 随着博主文案积累，学到的词越来越准确，灵感越来越像
- 完整叙事：起因→经过→结果
"""
import json, os, re, random
from datetime import datetime, timezone

# 基于脚本所在目录定位，避免硬编码 Windows 路径导致 Linux CI (GitHub Actions) 找不到文件而报错跳过
WORK = os.path.dirname(os.path.abspath(__file__))
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

def select_topics(data, n=60):
    """按爆火度排名前 n 条（动态，不再固定200）。
    用户要求：灵感不固定条数，只放容易火的、按爆火度排名前。
    有真实摘要的文章小幅加权，提升灵感文案质量（避免空壳）。
    """
    arts = [a for a in data.get("articles",[]) if a.get("source")!="blogger"]
    seen = set(); uni = []
    def key_fn(a):
        s = douyin_score(a)
        if a.get("summary") and len(str(a.get("summary")).strip()) > 15:
            s += 8
        return s
    for a in sorted(arts, key=key_fn, reverse=True):
        t = a.get("title","")
        if t and t not in seen:
            seen.add(t); uni.append(a)
    return uni[:n]

def parse_event(summary, topic=""):
    """把summary拆成起因+经过+结果；若summary只是标题复述/热搜前缀则返回空"""
    s = clean_text(summary or "")
    # 剔除热搜平台前缀（如「抖音热搜:」「微博热搜」）
    s = re.sub(r'^(抖音热搜|微博热搜|百度热搜|知乎热榜|今日头条|热搜|热榜)[:：]?\s*', '', s).strip()
    if not s: return {"cause":"", "detail":"", "result":""}
    sents = [x.strip() for x in re.split(r'[。；]', s) if len(x.strip())>10]
    if not sents:
        return {"cause":"", "detail":"", "result":""}
    cause = sents[0]
    # 若首句以话题开头（话题复述+扩展），去掉话题前缀，避免文案重复
    if topic and cause.startswith(topic):
        cause = cause[len(topic):].lstrip('：:，, 。　 ')
        if not cause:
            return {"cause":"", "detail":"", "result":""}
    # 首句基本就是话题本身的复述（无额外信息）→ 视为无真实内容
    elif topic and len(cause) <= len(topic)+8 and topic[:min(8,len(topic))] in cause:
        return {"cause":"", "detail":"", "result":""}
    return {
        "cause": cause,
        "detail": sents[1] if len(sents)>=2 else "",
        "result": sents[2] if len(sents)>=3 else (sents[1] if len(sents)>=2 else ""),
    }

def _fit(text, maxlen=150):
    """将文案截断到 maxlen 字内（按标点优雅截断，避免生硬切断），符合 REQUIREMENTS 80-150字要求"""
    text = (text or "").strip()
    if len(text) <= maxlen:
        return text
    # 在 maxlen 内向前找最近的中文/英文标点作为截断点
    for i in range(maxlen, max(0, maxlen - 50), -1):
        if text[i] in "。！？!?，,；;":
            return text[:i+1].rstrip("，,、；;") + "。"
    return text[:maxlen].rstrip("，,、；;") + "。"

# ═══════════════════════════════════════════════════════
#  基于持续学习风格词 + 完整叙事结构 生成
# ═══════════════════════════════════════════════════════

def wangba_write(topic, event, style):
    """网吧信息差：起因→经过→结果 + 评论 + 互动（精简到80-150字）"""
    today = datetime.now().strftime("%m月%d日")
    trans = pick(style.get("connectors",["不过"]), topic+"_trans")

    opens = [
        f"先说{today}呢，巴沙是真没想到，{topic}。",
        f"说到吧，{today}，咱先聊{topic}。",
        f"说回新闻，{today}头一个，{topic}。",
    ]
    opening = pick(opens, topic+"_open")

    cause = event.get("cause","") or ""
    detail = event.get("detail","") or ""
    result = event.get("result","") or ""

    # 口语化改写（仅当有真实摘要时）
    if cause:
        for old, new in [("经审理查明：","简单来说就是，"),("经调查","据了解"),
                          ("据报道","说是啊"),("据悉","听说啊"),("目前","截止到现在啊"),
                          ("近日","就这两天"),("人民法院","法院"),("被告人","这哥们"),
                          ("非法收受财物","贪了"),("判处死刑","直接判了死刑")]:
            cause = cause.replace(old, new)

    # 有真实摘要才展开叙事，否则克制陈述；story 限长防超150
    if cause or detail or result:
        story = f"起因——{cause or topic}。"
        if detail: story += f"{detail}。"
        if result: story += f"结果呢——{result}。"
        story = story[:72]
    else:
        story = "这事儿最近传得挺凶，巴沙帮大家理一遍。"

    ends = [
        "你们遇过类似的不？评论区聊聊。",
        "OK下件事，评论区说说看法。",
        "巴沙后续跟进，评论区聊聊。",
    ]
    end = pick(ends, topic+"_end")

    return _fit(f"{opening}{story}那听到这儿，评论区已经炸了，网友们直接绷不住了。{end}")

def aqi_write(topic, event, style):
    """阿七纪录片：起因+各方反应+信息差（精简到80-150字）"""
    today = datetime.now().strftime("%m月%d日")
    trans = pick(style.get("connectors",["不过"]), topic+"_trans")
    cause = event.get("cause","") or ""
    detail = event.get("detail","") or ""
    result = event.get("result","") or ""

    if cause or detail or result:
        story = f"事情是这样的——{cause or topic}。"
        if detail: story += f"{detail}。"
        if result: story += f"后续——{result}。"
        story = story[:60]
    else:
        story = "这事儿最近传得挺凶。"

    return _fit(f"{today}社会热点信息差。今天聊件没深扒的事：{topic}。{story}{trans}，微博讲情绪，知乎讲逻辑，事实的另一半在信息差里。你怎么看？")

def chen_write(topic, event, style):
    """陈先生：事件+数据+反转（精简到80-150字）"""
    cause = event.get("cause","") or ""
    result = event.get("result","") or ""
    trans = pick(style.get("connectors",["不过"]), topic+"_trans")
    kw = topic[:18]

    if cause or result:
        story = f"{cause or topic}。"
        if result: story += f"{result}。"
        story = story[:55]
    else:
        story = "这事儿最近传得挺凶，我帮你捋一下。"

    return _fit(f"大型纪录片之《{kw}》持续播出。{story}讲真的，{trans}，这事发生我一点不意外——过去几个月类似的不是第一次。数字摆在那，你怎么看？")

def guancha_write(topic, event, style):
    """人类观察菌：客观事实+多版本（精简到80-150字）"""
    cause = event.get("cause","") or topic
    result = event.get("result","")
    story = f"先说事实——{cause}。"
    if result: story += f"{result}。"
    story = story[:55]

    return _fit(f"今日热点信息快报。{story}有意思的来了：官方、当事人、网友，三个版本三个世界。我不说谁对谁错，公开信息放下面，你自己比对。评论区聊聊你的分析。")

def shadi_write(topic, event, style):
    """沙漠一之雕：快节奏播报（精简到80-150字）"""
    today = datetime.now().strftime("%m月%d日")
    cause = event.get("cause","") or ""
    result = event.get("result","") or ""

    if cause or result:
        story = f"{cause}。"
        if result: story += f"{result}。"
        story = story[:45]
    else:
        story = "这事儿最近传得挺凶，简单捋一下。"

    return _fit(f"一夜之间发生了啥？{today}热点快报。第一条——{topic}。{story}目前还在发酵，后续值得盯。评论区一人一句。")

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
    topics = select_topics(data)
    print(f"\n筛选 {len(topics)} 个高爆火话题\n")
    
    writers = {"wangba": wangba_write, "aqi": aqi_write, "chen": chen_write,
               "guancha": guancha_write, "shadi": shadi_write}
    
    inspirations = []
    for a in topics:
        topic = a.get("title","")
        summary = a.get("summary","")
        if not topic: continue
        
        event = parse_event(summary, topic)
        insp = {"topic": topic, "source": a.get("source",""), "url": a.get("url","") or "", "score": douyin_score(a)}
        
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
