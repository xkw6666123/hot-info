# -*- coding: utf-8 -*-
"""一次性：清洗已生成灵感里的人格串味（其他博主名混入），清洗不掉的用 LLM 重生成该字段。"""
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)

from llm_inspiration import generate_llm_inspiration, BLOGGER_HINTS

FIELDS = {"wangba": "网吧信息差", "aqi": "阿七大型纪录片", "chen": "陈先生",
          "guancha": "人类观察菌", "shadi": "沙漠一之雕"}


def clean_text(t):
    t = t.replace("阿七大型纪录片之《", "大型纪录片之《").replace("阿七大型纪录片《", "大型纪录片《")
    return t


def contaminated(t, own):
    return any(n in t for n in BLOGGER_HINTS if n != own)


def main():
    data = json.load(open("data.json", encoding="utf-8-sig"))
    insp = data["inspirations"]
    styles = json.load(open("deep_style_learned.json", encoding="utf-8"))

    # 1. 先做无害替换，再统计仍串味的字段
    todo = []  # (insp_idx, field, blogger)
    for idx, it in enumerate(insp):
        for f, own in FIELDS.items():
            t = it.get(f, "")
            if not t:
                continue
            t2 = clean_text(t)
            it[f] = t2
            if contaminated(t2, own):
                todo.append((idx, f, own))
    print(f"无害替换后仍串味字段: {len(todo)} 个", flush=True)

    # 2. 并行重生成
    def regen(item):
        idx, f, own = item
        topic = re.sub(r"#\S+", "", re.sub(r"\[.*?\]", "", insp[idx].get("topic", ""))).strip()[:60]
        summary = (insp[idx].get("summary") or "")[:200]
        for _ in range(2):
            try:
                out = generate_llm_inspiration(own, styles.get(own, {}), topic, summary=summary)
            except Exception:
                out = None
            if out and not contaminated(out, own):
                return idx, f, out
        return idx, f, None

    fixed = failed = 0
    if todo:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for idx, f, out in ex.map(regen, todo):
                if out:
                    insp[idx][f] = out
                    fixed += 1
                else:
                    failed += 1
        print(f"重生成: 成功 {fixed} / 失败 {failed}", flush=True)

    data["inspirations"] = insp
    json.dump(data, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 最终校验
    left = sum(1 for it in insp for f, own in FIELDS.items() if contaminated(it.get(f, ""), own))
    print(f"最终仍串味字段: {left}", flush=True)


if __name__ == "__main__":
    main()
