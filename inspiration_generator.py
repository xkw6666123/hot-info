#!/usr/bin/env python3
"""
灵感生成器 v5 —— 严格按博主创作指南规则生成
- 网吧信息差：极短悬念标题 + 固定标签（标题即全部文案）
- 阿七大型纪录片：信息差视角，逐条分析
- 其他博主：按各自指南规则
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

def extract_kw(topic, n=12):
    topic = re.sub(r'#\S+', '', topic).strip('，。！？；、:： ')
    for sep in '，。！？；、:： ':
        idx = topic.find(sep)
        if 3 <= idx <= n:
            return topic[:idx]
    return topic[:n] if len(topic) > n else topic

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
#  各博主创作规则
# ═══════════════════════════════════════════════════════

def wangba_insp(topic):
    """网吧信息差风格：极短悬念标题 + 固定标签"""
    kw = extract_kw(topic)
    
    titles = [
        f"不是，{kw}？",
        f"标题：{kw}，这合理吗？",
        f"{kw} 居然是真的",
        f"能理解 能理解 {kw}",
        f"谁还记得{kw}？",
        f"不是我说，{kw}？",
        f"《{kw}》",
        f"{kw} 没完了是吧",
        f"你说{kw}？？",
        f"这{kw}？我真服了",
    ]
    random.seed(topic + "wb")
    title = random.choice(titles)
    tags = "#青年创作者成长计划 #内容过于真实 #大学生 #热点"
    return f"{title}\n{tags}"

def aqi_insp(topic):
    """阿七纪录片风格：信息差视角，逐条分析"""
    kw = extract_kw(topic)
    today = datetime.now().strftime("%m月%d日")
    
    templates = [
        f"{today}社会热点信息差。今天先讲一个很多人只看了一眼标题就划走的事：{topic}。你可能觉得这跟你没什么关系，但巴沙帮你理了三条线：一是这件事的时间线其实比报道里说的要早将近一周；二是当事人的回应方式本身就很有意思；三是这件事背后涉及的人群比表面上多得多。这就是信息差——你看的是新闻，别人看的是信号。",
        f"热点信息差。{topic}——这条新闻今天在全网刷到的人应该不少，但是你有没有注意到，不同平台在讲同一件事的时候，侧重点完全不一样？微博在强调情绪，知乎在分析逻辑，评论区的大哥在科普背景。巴沙花了半天把这些版本都看了一遍，发现每个版本都只说了一半的事实。另一半在哪里？在这条视频里。",
        f"{today}，巴沙今天想讲一个其实挺重要但没什么人深聊的事：{topic}。这类新闻有一个共同特点——标题很平淡，点进去才发现水很深。我分三个角度帮你看：时间、人物、潜在影响。第一个角度——第二个角度——第三个——好了，信息给你了。每天一条信息差，你就比99%的人多知道一点。",
        f"为什么{topic}？因为大部分人都被标题带偏了。巴沙翻了一上午原始资料，发现最早的消息源其实不是你们看到的那个账号，而是一个几乎没人关注的小号。然后这条信息经过了三次转手，每转一次就变一次意思，到了热搜上的时候已经面目全非。这个过程本身就是一个经典的信息差案例。",
        f"今天全网都在讨论{topic}，但没几个人把关键节点说清楚。巴沙直接给你画时间线：第一阶段——第二阶段——反转点——现状——。你把这个时间线记住，下次再有人跟你聊这个事，你就不会被带节奏了。记住巴沙一句话：看新闻永远要看谁在说、对谁说、为什么这时候说。",
    ]
    random.seed(topic + "aq")
    return random.choice(templates)

def chen_insp(topic):
    """陈先生风格：商业纪录片口吻"""
    kw = extract_kw(topic)
    
    is_biz = any(w in topic for w in ['上市','降价','新品','发布','收购','手机','车','股','芯片','AI','裁员','融资','世界杯','比赛'])
    
    if is_biz:
        templates = [
            f"大型纪录片之《{kw}》持续为您播出。{topic}，这件事如果放在三年前，没有人会信。但现在它真实地发生了。不是因为运气好，是因为整个行业走到了一个拐点。以前大家想的是怎么做大，现在所有人都在想怎么活下去。活下去的办法就一条——把东西做好，把价格打下来。不玩虚的。",
            f"这波真的不讲武德。{topic}。我理解为什么很多人说不可能——因为按照常规思路这件事确实不可能。但是这次人家走的路跟你想象的不太一样。过去大家挤在一条赛道上卷，卷到最后谁都赚不到钱。现在有人换了一条路——不是更好，是更对。数据不会骗人，你自己去看。",
            f"来讲一个正在发生的产业变革：{topic}。很多人看新闻只看标题，但其实这条新闻背后有三个信号：第一，产业链上游在重构；第二，终端定价逻辑在变；第三，消费者的预期被重新教育了。任何一个信号单独看都不算什么，三个信号一起出现——这就不是偶然了。",
        ]
    else:
        templates = [
            f"大型纪录片之《{kw}》。{topic}，讲真的，这个事发生的时候我一点都不意外。因为在过去的三个月里，类似的事情已经有四五起了。大家觉得这是小概率事件，其实完全不是——只是以前没人统计罢了。现在统计出来了，数字摆在那里，不信也得信。这就是我说的——大数据时代，没有秘密。",
            f"今天讲一个现象级的新闻：{topic}。我翻了一下评论区，点赞最高的三条评论分别代表了三种完全不同的立场。有意思的不是他们说了什么，而是他们的点赞数——你会发现这场争论其实没有赢家，每个人的观点都被一半的人支持、一半的人反对。这种撕裂感，在最近的热搜里越来越常见了。",
            f"《{kw}》这部纪录片更新了。{topic}。说大不大说小不小，但我注意到的不是事情本身，是各方的反应。甲方说——乙方回应——第三方插了一句——你看出来了吗？这里面有一个很微妙的权力结构。这是真实的中国互联网，比任何剧本都精彩。",
        ]
    random.seed(topic + "ch")
    return random.choice(templates)

def guancha_insp(topic):
    """人类观察菌风格：冷静观察，摆事实"""
    kw = extract_kw(topic)
    
    templates = [
        f"今日热点快报：{kw}。先说基本事实——{topic}，这是目前可以确认的。然后有意思的部分来了：官方说的是A，当事人说的是B，网友说的是C。三个版本，三个世界。我不告诉你谁对谁错，我把所有能找到的公开信息放在下面，你自己比对，自己判断。",
        f"一条热乎的新闻：{topic}。根据目前已经公开的信息，我整理了这样一个时间线——最开始是——然后是——转折出现在——现在的状态是——。你看完这条时间线，有没有觉得哪里不对劲？如果有，评论区告诉我你注意到的是什么。",
        f"热点快报，先看数据：{topic}。说一下我注意到的三个细节，其他报道基本都只提了第一个。细节一——细节二——细节三——。这三个细节连起来，指向一个不太一样的方向。今天我不给结论，只呈现信息，结论交给你。",
        f"今天观察到一个有趣的现象：{topic}。我打开微博评论区看了前五十条——大概60%的人说——30%的人说——剩下10%在问别的事情。这个比例本身就是一个信号。你觉得这个比例说明了什么？来评论区聊聊你的分析。",
        f"快报时间。{topic}。收集了公开信息整理了一下前后脉络：起因→发展→各方回应→最新进展。好了打出来给你们了。我今天不想评价，因为我觉得这件事的答案不在任何一方的说法里，在那些还没被说出来的信息里。评论区聊聊你的视角。",
    ]
    random.seed(topic + "gc")
    return random.choice(templates)

def shadi_insp(topic):
    """沙漠一之雕风格：快节奏连播"""
    kw = extract_kw(topic)
    today = datetime.now().strftime("%m月%d日")
    
    templates = [
        f"一夜之间发生了啥？{today}热点快报。第一条——{topic}。起因很简单，但后面发生的事完全出乎意料。事情是这样的：最早是——结果没过多久——然后今天上午——。大家现在最关心的问题是——这个问题的答案可能比你想的复杂。来评论区一人一句。",
        f"{today}热点开唠。昨天晚上到今天全网最热闹的新闻：{topic}。给还没看的朋友用一句话说清楚——{topic}。如果你觉得这件事就是一个简单的A导致B，那可能要重新想想了。因为它后面的逻辑其实是一条链：从A到B到C到D，中间每个环节都有人在操作。这不是一个人的事，是一群人的事。",
        f"用两分钟给你补完今天的热搜，先说最火的一个：{topic}。目前我看到的最新情况是这样——但是如果你往回翻翻时间线，你会发现事情在三天前就已经有苗头了。为什么三天前没人关注？因为那时候信息还太碎，没人拼起来。巴沙今天帮你拼好了。",
        f"来，今天的热点按时间串一下：{topic}。早上——下午——傍晚——。一天之内，事情变了三回。每回都不一样。你如果只看中午的报道，你会得出一个完全相反的结论。这就是为什么你需要信息差——不是比别人快，是比别人全。",
        f"补一下今天的热搜。{topic}。先说结论：这件事现在还在发酵中，后面的走向还没定。但是有几点是确定的——第一——第二——第三——。这三点不管后面怎么变，都不会变。因为这是事实，不是观点。好，下一条——",
    ]
    random.seed(topic + "sd")
    return random.choice(templates)

def main():
    print("=== 灵感生成器 v5 ===\n")
    data = load_json(DATA_FILE)
    topics = select_topics(data, n=200)
    print(f"筛选出 {len(topics)} 个高爆火潜力话题\n")
    
    inspirations = []
    for a in topics:
        topic = a.get("title", "")
        source = a.get("source", "")
        if not topic:
            continue
        insp = {
            "topic": topic, "source": source,
            "blogger_name": a.get("blogger_name", ""),
            "score": douyin_score(a),
            "wangba": wangba_insp(topic),
            "aqi": aqi_insp(topic),
            "chen": chen_insp(topic),
            "guancha": guancha_insp(topic),
            "shadi": shadi_insp(topic),
        }
        inspirations.append(insp)
    
    inspirations.sort(key=lambda x: x.get("score", 0), reverse=True)
    data["inspirations"] = inspirations
    data["updated_at"] = datetime.now().isoformat()
    save_json(DATA_FILE, data)
    
    print(f"✅ 已生成 {len(inspirations)} 条灵感")
    print(f"   前3: {', '.join([i['topic'][:15] for i in inspirations[:3]])}")

if __name__ == "__main__":
    main()
