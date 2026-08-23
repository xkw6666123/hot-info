# -*- coding: utf-8 -*-
"""一次性（2026-08-23）：合并后最终验证"""
import json, re, sys
sys.stdout.reconfigure(encoding="utf-8")

data = json.load(open("data.json", encoding="utf-8-sig"))
FIELDS = {"wangba": "网吧信息差", "aqi": "阿七大型纪录片", "chen": "陈先生",
          "guancha": "人类观察菌", "shadi": "沙漠一之雕"}
NAMES = list(FIELDS.values())

# 1. 串味
bad = 0
for it in data.get("inspirations", []):
    for f, own in FIELDS.items():
        t = it.get(f, "") or ""
        for n in NAMES:
            if n != own and n in t:
                bad += 1
print("1. 灵感串味字段:", bad)

# 2. 博主
from collections import Counter
bl = [a for a in data["articles"] if a.get("source") == "blogger"]
print("2. 博主条数:", dict(Counter(a.get("blogger_name") for a in bl)))
pinned = [a["title"][:20] for a in bl if "分享一些短视频心得" in (a.get("title") or "")]
print("   置顶杂帖残留:", len(pinned))
fake_today = [a.get("blogger_name") for a in bl if a.get("date") == "2026-08-23"]
print("   date被盖成今天的博主条目:", len(fake_today))

# 3. 灵感质量
insp = data.get("inspirations", [])
empty = sum(1 for it in insp for f in FIELDS if not (it.get(f) or "").strip())
no_summary = sum(1 for it in insp if not (it.get("summary") or "").strip())
print(f"3. 灵感: {len(insp)} 条 | 空文案字段: {empty} | 无素材summary: {no_summary}")
date_open = 0
for it in insp:
    for f, own in FIELDS.items():
        if own == "阿七大型纪录片":
            continue
        t = (it.get(f) or "")
        if re.match(r"^\s*\d{1,2}月\d{1,2}日", t):
            date_open += 1
print("   非阿七日期开头:", date_open)

# 4. 新闻新鲜度（远端今日新闻保留）
news = [a for a in data["articles"] if a.get("source") != "blogger"]
dates = Counter((a.get("date") or "")[:10] for a in news)
recent = {d: c for d, c in sorted(dates.items()) if d >= "2026-08-22"}
print("4. 近两天新闻:", recent)
print("   新闻总数:", len(news), "| 文章总数:", len(data["articles"]))

# 5. JS 同步
js = open("data.js", encoding="utf-8").read()
insp_js = open("inspiration.js", encoding="utf-8").read()
html = open("index.html", encoding="utf-8").read()
jdata = json.loads(js.rstrip()[:-1][len("window.__HOT_DATA__="):])
jinsp = json.loads(insp_js.rstrip()[:-1][len("window.__INSP_DATA__="):])
print("5. data.js 文章数:", len(jdata["articles"]), "| inspiration.js 灵感数:", len(jinsp))
v = re.search(r"data\.js\?v=(\d+)", html).group(1)
dv = re.search(r"__DATA_VERSION__='(\d+)'", html).group(1)
print("   index.html 版本引用:", v, "| __DATA_VERSION__:", dv)
jbl = [a for a in jdata["articles"] if a.get("source") == "blogger"]
print("   data.js 博主条数:", len(jbl), "| inspiration_count:", jdata.get("inspiration_count"))

# 6. 代码修复版本确认
gh = open("generate_hot.py", encoding="utf-8").read()
li = open("llm_inspiration.py", encoding="utf-8").read()
dsl = open("deep_style_learner.py", encoding="utf-8").read()
print("6. generate_hot 含置顶过滤:", "is_top" in gh, "| 含话题质量过滤:", "_has_substance" in gh)
sig = 'def generate_llm_inspiration(blogger_name, style, topic, max_retry=2, summary="")'
print("   llm_inspiration 含 summary 透传:", sig in li)
sig2 = 'def generate_inspiration_from_deep_style(topic, source, styles, summary="")'
print("   deep_style_learner 含 summary 透传:", sig2 in dsl)
