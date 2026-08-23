# -*- coding: utf-8 -*-
"""并行重生成灵感库（2026-08-22）：GLM 串行一次 11s 太慢，6 线程并行 ≈ 8 分钟。
流程：打分筛选具体话题 → 每话题 5 博主并行模仿生成 → 失败回退模板 → 写回 data.json"""
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)

import generate_hot as g
from llm_inspiration import generate_llm_inspiration

TOPIC_CAP = int(os.environ.get("INSP_TOPICS", "45"))   # 话题数上限
WORKERS = 6

_GENERIC_TITLES = {
    "今日热点信息快报", "今日热点快报", "热点快报", "热点信息差", "社会热点信息差",
    "今日热点", "热点新闻", "每日热点", "今日新闻", "热点合集", "最新视频",
}

def has_substance(title):
    t = re.sub(r"\[.*?\]", "", title or "")
    t = re.sub(r"#\S+", "", t).strip(" ，。！？、:：")
    return len(t) >= 8 and t not in _GENERIC_TITLES


def main():
    t0 = time.time()
    data = json.load(open("data.json", encoding="utf-8-sig"))
    arts = data["articles"]

    # 1. 打分筛选（与 generate_inspirations 同规则）
    scored = sorted(((g.douyin_score(a), a) for a in arts), key=lambda x: x[0], reverse=True)
    selected, seen_src = [], {}
    for s, a in scored:
        if s < 58 or not has_substance(a.get("title", "")):
            continue
        src = a.get("source", "其他")
        if src == "blogger" or seen_src.get(src, 0) < 8:
            selected.append(a)
            seen_src[src] = seen_src.get(src, 0) + 1
        if len(selected) >= TOPIC_CAP:
            break
    print(f"话题筛选: {len(selected)} 条", flush=True)

    # 2. 加载风格指纹
    styles = json.load(open("deep_style_learned.json", encoding="utf-8"))
    bloggers = ["网吧信息差", "阿七大型纪录片", "陈先生", "人类观察菌", "沙漠一之雕"]
    field = {"网吧信息差": "wangba", "阿七大型纪录片": "aqi", "陈先生": "chen",
             "人类观察菌": "guancha", "沙漠一之雕": "shadi"}

    from deep_style_learner import generate_inspiration_from_deep_style as gen_func

    def gen_one(blogger, clean_topic, summary):
        try:
            return generate_llm_inspiration(blogger, styles.get(blogger, {}), clean_topic, summary=summary)
        except Exception:
            return None

    inspirations = []
    done = 0
    for a in selected:
        topic = a.get("title", "")
        source = a.get("source", "")
        clean = re.sub(r"#\S+", "", re.sub(r"\[.*?\]", "", topic)).strip()[:60]
        summary = (a.get("summary") or "")[:200]
        entry = {
            "topic": topic, "source": source,
            "blogger_name": a.get("blogger_name", ""),
            "url": a.get("url", ""),
            "hot_score": g.douyin_score(a),
            "summary": summary,
        }
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            results = list(ex.map(lambda b: gen_one(b, clean, summary), bloggers))
        missing = [b for b, r in zip(bloggers, results) if not r]
        for b, r in zip(bloggers, results):
            if r:
                entry[field[b]] = r
        if missing:
            # 模板兜底（只给缺的博主用模板，不重复调 LLM）
            try:
                import llm_inspiration as _li
                _li._call_count = _li._MAX_CALLS_PER_RUN  # 锁死 LLM，强制 gen_func 走模板
                tpl = gen_func(topic, source, styles, summary=summary)
            except Exception:
                tpl = {}
            for b in missing:
                entry[field[b]] = tpl.get(b, "")
        inspirations.append(entry)
        done += 1
        if done % 5 == 0 or done == len(selected):
            print(f"  进度 {done}/{len(selected)} ({time.time()-t0:.0f}s)", flush=True)

    data["inspirations"] = inspirations
    json.dump(data, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成: {len(inspirations)} 条灵感，耗时 {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
