# -*- coding: utf-8 -*-
"""LLM 灵感生成：调智谱 GLM-4-Flash，喂博主真实转录文案，模仿博主口吻写抖音文案。

设计原则：
- 只读不写，拿不到 key / API 失败 / 超时都返回 None（上层回退模板，绝不影响流水线）
- key 来源：环境变量 GLM_API_KEY 或 ZHIPU_API_KEY，其次项目目录 glm_key.txt
- 模型：glm-4-flash（智谱免费档，文案能力够用）
"""
import json, os, re, sys
from datetime import datetime

WORK = os.path.dirname(os.path.abspath(__file__))
GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_MODEL = "glm-4-flash"
TIMEOUT = 25

# 各博主人设提示（帮助 LLM 抓住差异化，而不是所有博主都一个味）
BLOGGER_HINTS = {
    "网吧信息差": "大学生视角的荒诞解构，爱用「不是，xxx？」「能理解能理解」，把严肃的事说得哭笑不得，带点自嘲",
    "阿七大型纪录片": "日期锚点式信息差播报，老记者口吻，爱说「先说结论」「巴沙帮你捋」，强调别人没看到的那层信息",
    "陈先生": "商业纪录片旁白腔，爱用「大型纪录片之《xxx》」，叙事宏大、讲商业逻辑和行业信号，自带BGM感",
    "人类观察菌": "冷静对话体，像在摆事实、呈现多个版本再让观众自己判断，爱说「先说基本事实」「三个版本三个世界」",
    "沙漠一之雕": "B站唠嗑式快报，快节奏连播、信息量大，爱说「一夜之间发生了啥」「来来来」「补一下今天的热搜」",
}

sys.stdout.reconfigure(encoding='utf-8')


def _load_key():
    """环境变量优先，其次项目目录 glm_key.txt"""
    for k in ("GLM_API_KEY", "ZHIPU_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    f = os.path.join(WORK, "glm_key.txt")
    if os.path.exists(f):
        try:
            return open(f, "r", encoding="utf-8").read().strip()
        except Exception:
            pass
    return ""


def _clean_topic(topic):
    t = re.sub(r"\[.*?\]", "", topic or "")
    t = re.sub(r"#[^\s#]+", "", t)
    return t.strip()[:60]


_TRANSCRIPTS_CACHE = None

# 每次运行的 LLM 调用预算（默认 50 ≈ 10 话题×5 博主；免费 token 约够跑一个月）
_MAX_CALLS_PER_RUN = int(os.environ.get("LLM_MAX_CALLS", "50"))
_call_count = 0


def _load_transcripts():
    """加载 asr_content.json 的完整真实转录（ASR 持续累积），按博主分组。
    返回 {blogger_name: [content_intro, ...]}。这是"一直学习越来越像"的原料：
    每天的 ASR 新转录都会进 asr_content.json，LLM 每次读到的都是最新最全的真实文案。"""
    global _TRANSCRIPTS_CACHE
    if _TRANSCRIPTS_CACHE is not None:
        return _TRANSCRIPTS_CACHE
    result = {}
    f = os.path.join(WORK, "asr_content.json")
    if os.path.exists(f):
        try:
            d = json.load(open(f, "r", encoding="utf-8"))
            items = d.values() if isinstance(d, dict) else d
            for it in items:
                if not isinstance(it, dict):
                    continue
                name = it.get("blogger_name", "")
                ci = (it.get("content_intro") or "").strip()
                if name and len(ci) >= 120:
                    result.setdefault(name, []).append(ci)
        except Exception:
            pass
    _TRANSCRIPTS_CACHE = result
    return result


def _build_prompt(blogger_name, style, topic):
    """构建模仿 prompt：RAG 检索"该博主讲相似话题"的真实口播为主 + 口头禅/开场收尾为辅。
    返回 (system, user, samples)：samples 是喂给模型的原始样本（供照抄检测用）。"""
    # 主素材：RAG 检索与当前话题最相似的该博主历史口播（像"博主讲这类话题时"的样子）
    excerpts = []
    try:
        from rag_store import retrieve
        excerpts = [t[:600] for t in retrieve(blogger_name, topic, top_k=2)]
    except Exception:
        excerpts = []
    if not excerpts:
        # 回退：该博主最新几条完整转录
        full_txts = _load_transcripts().get(blogger_name, [])
        excerpts = [ci[:600] for ci in full_txts[-3:]]
    samples = list(excerpts)
    if excerpts:
        sample_txt = "\n---\n".join(excerpts)
    else:
        # 兜底：用 deep_style_learned.json 提取的句式
        sp = [s for s in (style.get("sentence_patterns") or []) if isinstance(s, str) and len(s) >= 6][:12]
        sample_txt = "\n".join(f"· {s}" for s in sp) or "（暂无样本）"

    voc = style.get("vocabulary") or {}
    vocab_str = "、".join(
        (voc.get("transitions") or [])[:6] + (voc.get("interactions") or [])[:6]
    ) or "无"
    openings_list = [s for s in (style.get("top_openings") or []) if isinstance(s, str) and len(s) >= 6][:4]
    endings_list = [s for s in (style.get("top_endings") or []) if isinstance(s, str) and len(s) >= 6][:4]
    openings = "；".join(openings_list)
    endings = "；".join(endings_list)
    # 照抄检测的完整源：口播节选 + 开场 + 收尾（LLM 可能从任何一段原样搬句子）
    source_texts = samples + openings_list + endings_list

    sys_p = (
        "你是一位顶级抖音文案写手，最擅长一比一模仿某位博主的语言风格。"
        "你能精准抓住一个人的口头禅、语气、句式节奏和情绪，并写出别人分辨不出是不是本人发的文案。"
    )
    hint = BLOGGER_HINTS.get(blogger_name, "")
    hint_line = f"\n【TA 的人设/风格】{hint}" if hint else ""
    today_cn = datetime.now().strftime("%Y年%m月%d日")
    user_p = f"""今天是 {today_cn}。下面是抖音博主「{blogger_name}」真实视频的完整口播转录（最能代表 TA 的口吻、用词和说话节奏，请重点学习）：

【博主真实口播文案】
{sample_txt}

【TA 常用的口头禅 / 语气词】{vocab_str}
【TA 典型的开场方式】{openings}
【TA 典型的收尾方式】{endings}{hint_line}

现在请完全代入「{blogger_name}」这个人，针对下面这个话题写一条抖音视频文案：
话题：{topic}

要求：
1. 必须就是 TA 本人的口吻——读到的人会觉得"这就是{blogger_name}写的"，不要套话、不要官方腔、不要书面腔
2. 上面的真实口播讲的是别的具体事件，**只学它的口吻、句式、节奏和口头禅，绝不照抄里面的事件/人名/数字**，你要写的是新话题
3. 口语化、真实、有趣，像在跟粉丝唠嗑；可以有观点、有吐槽、有情绪，别干巴巴陈述事实
4. 若 TA 习惯用日期开头，务必用今天（{today_cn}）的真实日期，不要瞎编日期
5. 结尾学 TA 真实收尾的**腔调和句式节奏**，但内容必须贴合当前话题；**严禁把示例文案里的任何句子原样搬进你的文案**（那些是别的视频的原话，跟新话题无关）；也禁止"评论区聊聊/你们觉得呢"这类任何博主都能说的通用互动语
6. 长度控制在 60~140 字
7. 只输出文案本身，不要任何解释、标题、引号、前缀标签或多余的话"""
    return sys_p, user_p, source_texts


def _has_verbatim_copy(text, samples, n=18):
    """防照抄保险：输出里若有 n 字以上与源文本逐字相同的长片段 → 判定照抄。
    n=18：拦整句搬运（多带无关事件），放行 15 字以内的口头禅/惯用语重用（那是好的模仿）。"""
    if not samples or len(text) < n:
        return False
    for i in range(0, len(text) - n + 1):
        chunk = text[i:i + n]
        for s in samples:
            if chunk in s:
                return True
    return False


def _post(url, payload, key):
    """GLM OpenAI 兼容调用，返回文本或 None"""
    import requests
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"    ⚠️ GLM HTTP {r.status_code}: {r.text[:120]}", flush=True)
            return None
        j = r.json()
        content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return content.strip() or None
    except Exception as e:
        print(f"    ⚠️ GLM 调用异常: {type(e).__name__}: {str(e)[:100]}", flush=True)
        return None


def generate_llm_inspiration(blogger_name, style, topic, max_retry=2):
    """主入口：模仿博主生成一条文案。成功返回 str，失败返回 None（上层回退模板）

    配额保护：每次运行 LLM 调用数有上限（默认 50 次 ≈ 10 个话题×5 博主），
    超出后回退模板，防止免费 token 被一轮跑空。可用环境变量 LLM_MAX_CALLS 调整。"""
    global _call_count
    key = _load_key()
    if not key:
        return None  # 无 key → 回退
    if _call_count >= _MAX_CALLS_PER_RUN:
        return None  # 超出本次预算 → 回退模板
    clean = _clean_topic(topic)
    if not clean:
        return None

    sys_p, user_p, source_texts = _build_prompt(blogger_name, style, clean)
    payload = {
        "model": GLM_MODEL,
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_p},
        ],
        "temperature": 0.9,   # 高一点更活泼
        "top_p": 0.95,
        "max_tokens": 300,
    }
    for attempt in range(max_retry):
        _call_count += 1
        text = _post(GLM_URL, payload, key)
        if text:
            # 去掉可能残留的引号 / 【xxx】前缀标签 / 多余空白
            text = text.strip().strip('"').strip("“").strip("”").strip()
            text = re.sub(r'^【[^】]*】\s*', '', text).strip()
            # 清掉结尾偶发的英文乱码（如 GLM 幻觉出的 "dinero." / "Sorry"）
            text = re.sub(r'[A-Za-z]{3,}\s*\.?\s*$', '', text).strip()
            if len(text) >= 25 and _has_verbatim_copy(text, source_texts):
                print(f"    ⚠️ 检测到照抄原句，重试 ({attempt+1}/{max_retry})", flush=True)
                continue
            if len(text) >= 25:
                return text
    return None


if __name__ == "__main__":
    # 自测（无 key 时应直接返回 None，不报错）
    style = json.load(open(os.path.join(WORK, "deep_style_learned.json"), encoding="utf-8"))
    b = "网吧信息差"
    out = generate_llm_inspiration(b, style.get(b, {}), "大学生毕业进厂打工")
    print("LLM 输出:", repr(out))
