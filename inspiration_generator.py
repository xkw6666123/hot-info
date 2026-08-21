#!/usr/bin/env python3
"""
灵感生成器 v11 —— 真实博主语料风格指纹驱动
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
设计依据（REQUIREMENTS.md §4）：
- 风格学习：基于真实博主文案（blogger_content_archive.json 39条真人文案提炼）
- 模板类型：每博主 4-5 种结构，80-150字
- 质量要求：模仿真实人类叙述，无广告感

与 v10 的区别：
- v10 是"万能模板填空"：所有话题共用 3 开头+1 骨架+3 结尾，60条读下来像一台机器
- v11 是"风格指纹复刻"：每博主的真实开头习惯/口头禅/吐槽句式/收尾方式全部来自
  对真人文案的拆解，按 topic 哈希确定性组合，跨话题几乎不重样
"""
import json, os, re
from datetime import datetime

WORK = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(WORK, "data.json")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def hseed(*parts):
    """确定性哈希（跨运行一致），避免 random 模块的全局状态污染"""
    import hashlib
    s = "|".join(str(p) for p in parts)
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)


def pick(items, *seed_parts):
    if not items:
        return ""
    return items[hseed(*seed_parts) % len(items)]


def clean_text(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"[\n\r\t]", " ", s).strip()
    return s[:400]


def douyin_score(a):
    import math
    score = 0
    t = a.get("title", "")
    likes = a.get("likes", 0) or 0
    if likes > 0:
        score += min(35, math.log2(likes + 1) * 2)
    for w in ["泪崩", "震惊", "怒了", "崩溃", "炸裂", "反转", "意外", "惊人", "离谱", "逆天", "破防", "绷不住"]:
        if w in t:
            score += 12
            break
    for w in ["回应", "道歉", "曝光", "争议", "维权", "举报", "偷税", "造假"]:
        if w in t:
            score += 10
            break
    clean = re.sub(r"\[.*?\]|#\S+", "", t).strip()
    if len(clean) <= 12:
        score += 10
    boost = {"百度热搜": 8, "微博": 7, "知乎": 6, "bilibili": 6, "今日头条": 5}
    score += boost.get(a.get("source", ""), 2)
    return score


def select_topics(data, n=60):
    arts = [a for a in data.get("articles", []) if a.get("source") != "blogger"]
    seen = set()
    uni = []

    def key_fn(a):
        s = douyin_score(a)
        if a.get("summary") and len(str(a.get("summary")).strip()) > 15:
            s += 8
        return s

    for a in sorted(arts, key=key_fn, reverse=True):
        t = a.get("title", "")
        if t and t not in seen:
            seen.add(t)
            uni.append(a)
    return uni[:n]


def parse_event(summary, topic=""):
    """summary → {cause, detail, result}；无有效信息则全空"""
    s = clean_text(summary or "")
    s = re.sub(r"^(抖音热搜|微博热搜|百度热搜|知乎热榜|今日头条|热搜|热榜)[:：]?\s*", "", s).strip()
    if not s:
        return {"cause": "", "detail": "", "result": ""}
    sents = [x.strip() for x in re.split(r"[。；]", s) if len(x.strip()) > 10]
    if not sents:
        return {"cause": "", "detail": "", "result": ""}
    cause = sents[0]
    if topic and cause.startswith(topic):
        cause = cause[len(topic):].lstrip("：:，, 。　 ")
        if not cause:
            return {"cause": "", "detail": "", "result": ""}
    elif topic and len(cause) <= len(topic) + 8 and topic[:min(8, len(topic))] in cause:
        return {"cause": "", "detail": "", "result": ""}
    return {
        "cause": cause,
        "detail": sents[1] if len(sents) >= 2 else "",
        "result": sents[2] if len(sents) >= 3 else "",
    }


def _cut(text, maxlen):
    """按句读点优雅截断"""
    text = (text or "").strip()
    if len(text) <= maxlen:
        return text
    for i in range(maxlen - 1, max(0, maxlen - 30), -1):
        if text[i] in "。！？!?":
            return text[:i + 1]
    for i in range(maxlen - 1, max(0, maxlen - 30), -1):
        if text[i] in "，,；;":
            return text[:i].rstrip("，,、；;") + "。"
    return text[:maxlen].rstrip("，,、；;") + "。"


def _balance_quotes(text):
    """补全未闭合的中文引号（源摘要常有半开引号）"""
    if text.count("“") > text.count("”"):
        text += "”"
    if text.count("‘") > text.count("’"):
        text += "’"
    return text


def _fit(text, maxlen=150):
    text = (text or "").strip()
    if len(text) <= maxlen:
        return text
    out = text
    for i in range(maxlen, max(0, maxlen - 50), -1):
        if text[i] in "。！？!?，,；;":
            out = text[:i + 1].rstrip("，,、；;")
            break
    else:
        out = text[:maxlen].rstrip("，,、；;")
    if out and not out.endswith(("。", "！", "？", "!", "?", "”")):
        out += "。"
    elif out.endswith("”") and not out[:-1].endswith(("。", "！", "？", "!", "?")):
        out = out[:-1] + "。”"
    return out


def _tidy(text):
    """拼接后的标点规整：去叠句点、问号后句号、引号外句号等"""
    t = re.sub(r"([。！？!?])[。]+", r"\1", text or "")
    t = re.sub(r"([？！!?])。", r"\1", t)
    t = t.replace("。。”", "。”").replace("。。", "。").replace("，。", "。")
    return t


def _shares_phrase(a, b, n=5):
    """a 是否与 b 共享 ≥n 字的片段（用于句式池去重）"""
    if not a or not b:
        return False
    return any(a[j:j + n] in b for j in range(0, max(0, len(a) - n + 1), 2))


def pick_avoid(pool, avoid_text, *seed_parts):
    """从池中选一项，避开与 avoid_text 重复意象的项"""
    if not pool:
        return ""
    base = hseed(*seed_parts) % len(pool)
    for offset in range(len(pool)):
        cand = pool[(base + offset) % len(pool)]
        if not _shares_phrase(cand, avoid_text):
            return cand
    return pool[base]


def _kw(topic, n=20):
    """话题关键词（去书名号/标签/方括号，优雅截断，避免截断词）"""
    t = re.sub(r"[《》#\[\]]", "", topic or "").strip()
    if len(t) <= n:
        return t
    for i in range(n, max(0, n - 8), -1):
        if t[i] in "。！？!?，,；;、/":
            return t[:i].strip()
    return t[:n].strip()


def _story(event, topic, maxlen, mode="cause_first"):
    """把事件三要素拼成一段人话；无摘要时返回空串（由调用方走无料分支）"""
    cause, detail, result = event.get("cause", ""), event.get("detail", ""), event.get("result", "")
    if not (cause or detail or result):
        return ""
    parts = []
    if mode == "cause_first":
        parts.append(cause or topic)
        if detail:
            parts.append(detail)
        if result:
            parts.append(result)
    else:  # result_first：先抛结果再补经过（更像真人爆料）
        if result:
            parts.append(result)
        parts.append(cause or topic)
        if detail:
            parts.append(detail)
    return _balance_quotes(_cut("。".join(p for p in parts if p) + "。", maxlen))


def _date_cn():
    return datetime.now().strftime("%-m月%-d日") if os.name != "nt" else datetime.now().strftime("%m月%d日").lstrip("0").replace("月0", "月")


# ═══════════════════════════════════════════════════════════════
#  网吧信息差（巴沙）：大学生视角荒诞解构，日期锚点 + 事儿串联 + 神吐槽
#  真人语料特征："那么嘛，先说在…呢，首先第一个" / "说是啊" / "OK，下事儿" / "这事儿巴沙真都懒得喷"
# ═══════════════════════════════════════════════════════════════
def wangba_write(topic, event):
    d = _date_cn()
    k = _kw(topic)
    opener = pick([
        f"那么嘛，先说在{d}呢，首先第一个事儿，",
        f"说到吧，今天是{d}，咱先说头一个事儿，",
        f"说回到新闻，{d}头一个，",
        f"《新闻八点档》在{d}。首先第一个事儿，",
        f"说到八叉，今个儿{d}。先说第一个，",
        f"说到网上新闻呢，{d}。那首先第一个，",
    ], topic, "wb_open")
    lead = pick([
        f"{topic}，这事儿巴沙刷到的时候是真没想到",
        f"{topic}。说是啊，这事儿还真不是个段子",
        f"{topic}，巴沙本来以为又是编的，结果人正经上热搜了",
        f"就为{k}这事儿，网上从早上吵到现在",
        f"{topic}。这事儿听着离谱，但它偏偏是真的",
    ], topic, "wb_lead")
    react = pick([
        "哎，不过有意思的来了，评论区愣是没一个劝住的，全在添柴火",
        "那听到这儿，肯定有朋友反应过来了，这事儿怎么透着一股魔幻呢",
        "巴沙这么说啊，这事儿你细品，越想越不对劲儿",
        "说白了，这事儿巴沙真都懒得喷，槽点自己会长腿跑",
        "不过呀，好在评论区都是明白人，三言两语就把事儿理清了",
        "你别说，这事儿搁段子里都算编的，可它就是发生了",
    ], topic, "wb_react")
    end = pick([
        "具体怎么收场，咱们还是再等通报。那OK，下事儿。",
        "你们要是碰上这事儿会咋整？评论区聊聊。OK，下事儿。",
        "这事儿你们怎么看？反正巴沙是先笑为敬了。",
        "后续巴沙接着盯，有新动静第一时间唠。",
        "反正这事儿吧，离谱他妈给离谱开门了。",
    ], topic, "wb_end")
    story = _story(event, topic, 70, mode=pick(["cause_first", "result_first"], topic, "wb_mode"))
    if story:
        body = f"{lead}。{story}{react}。{end}"
    else:
        filler = pick([
            "细节还在陆续出来",
            "目前公开的就这么多，先别急着下结论",
            "这事儿前因后果，巴沙还没理太明白",
            "具体内情还没放出来，只有个标题在那挂着",
        ], topic, "wb_fill")
        body = f"{lead}。{filler}，{react}。{end}"
    return _tidy(_fit(opener + body))


# ═══════════════════════════════════════════════════════════════
#  阿七大型纪录片：日期锚点社会观察，金句前置 + 多视角 + 观点升华
#  真人语料特征："热点信息差，"直接抛事 / "OK，下一件事" / "说到底" / 神比喻
# ═══════════════════════════════════════════════════════════════
def aqi_write(topic, event):
    d = _date_cn()
    k = _kw(topic)
    opener = pick([
        f"{d}社会热点信息差。",
        f"{d}热点信息差，",
        f"热点信息差，{d}第一件事。",
        f"{d}社会热点信息差，先聊最值得扒的。",
    ], topic, "aq_open")
    lead = pick([
        f"{topic}",
        f"第一眼{kw_short(k)}，第二眼，这事儿没那么简单",
        f"{k}——刷到这条的时候，我承认我愣了一下",
        f"今天值得深扒的事：{topic}",
    ], topic, "aq_lead")
    view = pick([
        "微博讲情绪，知乎讲逻辑，事实的另一半在信息差里",
        "有人骂离谱，有人喊理解，可真正把事儿捋明白的没几个",
        "表面看是件小事，往深了扒，全是这个时代的切面",
        "评论区吵翻了，但吵来吵去，没人说到根上",
        "性别互换一下，这事儿的风评恐怕完全是另一个方向",
    ], topic, "aq_view")
    end = pick([
        "说到底，根子上的问题不解决，下次还会换个马甲再上热搜。",
        "事儿不大，但照见的东西不小。你怎么看？",
        "类似的剧本不是第一次上演，恐怕也不是最后一次。",
        "这就是信息差——你看到的是热闹，别人看到的是门道。",
        "具体的咱们还是等通报，但有一点可以肯定：这事儿没完。",
    ], topic, "aq_end")
    story = _story(event, topic, 65, mode="cause_first")
    if story:
        body = f"{lead}。{story}{view}。{end}"
    else:
        filler = pick([
            "细节还在发酵",
            "目前能确认的信息还不多",
            "完整经过还在陆续披露",
            "公开的部分还只是冰山一角",
        ], topic, "aq_fill")
        body = f"{lead}。{filler}，{view}。{end}"
    return _tidy(_fit(opener + body))


def kw_short(k, n=10):
    """短话题关键词：在标点或虚词前优雅截断，避免把"集体退场"切成"将集"这类断词"""
    k = (k or "").strip()
    if len(k) <= n:
        return k
    for i in range(n, max(0, n - 6), -1):
        if k[i] in "。！？!?，,；;、/ 将把要在是了的":
            return k[:i].strip()
    return k[:n].strip()


# ═══════════════════════════════════════════════════════════════
#  陈先生：纪录片腔商业/社会拆解，"好消息坏消息"对仗 + 数据 + 金句收尾
#  真人语料特征："好消息…坏消息…" / "你是说…吗？" / "起因是…" / "真的拭目以待了"
# ═══════════════════════════════════════════════════════════════
def chen_write(topic, event):
    k = _kw(topic)
    opener = pick([
        f"你是说{k}吗？这事儿要真成了，那可就有意思了",
        f"好消息，{kw_short(k)}有后续了。坏消息，后续比正传还精彩",
        f"一想到{k}这事儿，我就想笑。但你先别急着笑",
        f"大型纪录片之《{kw_short(k)}》持续播出",
        f"{k}。这事儿乍看是热闹，细看全是门道",
    ], topic, "ch_open")
    view = pick([
        "讲真的，这事发生我一点不意外——过去几个月，类似的剧本不是第一次",
        "一边是人情，一边是规则，夹在中间的滋味最难受",
        "数字摆在那，账其实很好算，就看有没有人愿意算",
        "都说外行看热闹，内行看门道，这回门道和热闹撞一块了",
    ], topic, "ch_view")
    end = pick_avoid([
        "这波究竟是偶然的乌龙，还是必然的结局？真的拭目以待了。",
        "账算到这份上，剩下的就看当事人怎么选了。",
        "也许一件小事改变不了什么，但人心的账，大家都记着呢。",
        "到底是哪个环节出了问题？答案可能就在每个人手里。",
        "纪录片的结尾还没写好，下一集更精彩。",
    ], view, topic, "ch_end")
    story = _story(event, topic, 60, mode="cause_first")
    if story:
        body = f"。{story}{view}。{end}"
    else:
        filler = pick([
            "细节还在陆续放出来",
            "目前能坐实的还不多",
            "更多内情还在路上",
            "公开信息还有缺口，别急着站队",
        ], topic, "ch_fill")
        body = f"。{filler}，{view}。{end}"
    return _tidy(_fit(opener + body))


# ═══════════════════════════════════════════════════════════════
#  人类观察菌：对话体人间观察，精确播报 + 模拟对话 + 毒舌点评 + 价值观收尾
#  真人语料特征："今日热点信息快报。" / 数字细节 / "我都能想象到…" / "而真正该共情的…"
# ═══════════════════════════════════════════════════════════════
def guancha_write(topic, event):
    k = _kw(topic)
    opener = pick([
        "今日热点信息快报。",
        "今日热点信息快报，",
    ], topic, "gc_open")
    lead = pick([
        f"{topic}",
        f"{k}——这事儿我盯了一天",
        f"先报事实：{topic}",
    ], topic, "gc_lead")
    dialogue = pick([
        "我都能想象到评论区会说什么了，无非就是那几句车轱辘话",
        "有意思的是，官方、当事人、网友，三个版本三个世界",
        "终于知道网络上跟你吵架的都是哪些人了",
        "我不说谁对谁错，公开信息放下面，你自己比对",
        "最魔幻的不是事儿本身，是评论区比事儿还精彩",
    ], topic, "gc_dlg")
    end = pick([
        "而真正该被看见的，是那些没上热搜的当事人。",
        "如果这事儿都能吵起来，那以后类似的事只会更多。",
        "评论区聊聊你的分析。",
        "细节都摆在这了，怎么判断，交给你。",
        "虽事不大，但是非不能颠倒。",
    ], topic, "gc_end")
    story = _story(event, topic, 60, mode="cause_first")
    if story:
        body = f"{lead}。{story}{dialogue}。{end}"
    else:
        filler = pick([
            "目前公开的信息还不多",
            "能核实的细节有限",
            "官方的说法还没出全",
            "目前只有这一版信息，先别下结论",
        ], topic, "gc_fill")
        body = f"{lead}。{filler}，{dialogue}。{end}"
    return _tidy(_fit(opener + body))


# ═══════════════════════════════════════════════════════════════
#  沙漠一之雕：B站东北唠嗑快报，"先唠第一件事" + 玩梗 + 夸张比喻
#  真人语料特征："X月X日热点快报，先唠第一件事" / "拉了坨大的" / "退一万步讲" / "合着小丑竟是我自己"
# ═══════════════════════════════════════════════════════════════
def shadi_write(topic, event):
    d = _date_cn()
    k = _kw(topic)
    opener = pick([
        f"{d}热点快报，先唠第一件事。",
        f"一夜之间发生了啥？{d}热点快报。先唠第一件事，",
        f"{d}热点快报。先聊第一件事，",
        f"睡了一觉起来，世界又变天了。{d}热点快报，",
    ], topic, "sd_open")
    lead = pick([
        f"{topic}",
        f"{k}，好家伙，我直接好家伙",
        f"刷到{k}这事儿，我饭都多吃了两碗",
        f"{topic}，离谱程度直接拉满",
    ], topic, "sd_lead")
    meme = pick([
        "退一万步讲，这事儿就没一个环节是正常的吗",
        "合着折腾半天，小丑竟是围观的我们自己",
        "这剧情的离谱程度，编剧来了都得递根烟",
        "本以为是在玩抽象，结果人当事儿办的",
        "只能说艺术来源于生活，但生活明显更敢编",
    ], topic, "sd_meme")
    end = pick([
        "目前还在发酵，后续值得盯。评论区一人一句。",
        "这事儿你站哪边？评论区唠五毛钱的。",
        "第一条就这样，后面的更刺激，咱们接着唠。",
        "行了，这事儿先唠到这，有啥新动静再补。",
    ], topic, "sd_end")
    story = _story(event, topic, 55, mode=pick(["cause_first", "result_first"], topic, "sd_mode"))
    if story:
        body = f"{lead}。{story}{meme}。{end}"
    else:
        filler = pick([
            "细节还不多",
            "目前就这点料，后续有猛料再补",
            "完整经过还没放出来",
            "现在知道的就这些，剩下的等通报",
        ], topic, "sd_fill")
        body = f"{lead}。{filler}，{meme}。{end}"
    return _tidy(_fit(opener + body))


def main():
    print("=== 灵感生成器 v11 真实风格指纹驱动 ===\n")
    data = load_json(DATA_FILE)
    topics = select_topics(data)
    print(f"筛选 {len(topics)} 个高爆火话题\n")

    inspirations = []
    for a in topics:
        topic = a.get("title", "")
        summary = a.get("summary", "")
        if not topic:
            continue
        event = parse_event(summary, topic)
        inspirations.append({
            "topic": topic,
            "source": a.get("source", ""),
            "url": a.get("url", "") or "",
            "hot_score": round(douyin_score(a)),
            "wangba": wangba_write(topic, event),
            "aqi": aqi_write(topic, event),
            "chen": chen_write(topic, event),
            "guancha": guancha_write(topic, event),
            "shadi": shadi_write(topic, event),
        })

    inspirations.sort(key=lambda x: x.get("hot_score", 0), reverse=True)
    data["inspirations"] = inspirations
    save_json(DATA_FILE, data)

    # 质量报告：长度分布 + 开头去重率
    def _lens(key):
        return [len(i[key]) for i in inspirations]
    print(f"✅ {len(inspirations)} 条灵感已生成")
    for key, label in [("wangba", "网吧"), ("aqi", "阿七"), ("chen", "陈先生"), ("guancha", "观察菌"), ("shadi", "沙漠")]:
        ls = _lens(key)
        opens = len({i[key][:12] for i in inspirations})
        over = sum(1 for l in ls if l > 150)
        under = sum(1 for l in ls if l < 60)
        print(f"  {label}: 平均{sum(ls)//len(ls)}字 | 超150:{over} 不足60:{under} | 开头去重 {opens}/{len(ls)}")
    ins = inspirations[0]
    print(f"\n样例【{ins['topic']}】")
    print(f"  网吧: {ins['wangba']}")
    print(f"  阿七: {ins['aqi']}")
    print(f"  沙漠: {ins['shadi']}")


if __name__ == "__main__":
    main()
