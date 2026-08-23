# -*- coding: utf-8 -*-
"""一次性修复博主视频数据（2026-08-22，v2）：

问题：
1. Playwright 兜底路径把 date 盖成抓取当天 → 阿七置顶老帖《分享一些短视频心得》被当成最新
2. 旧视频堆积（网吧信息差16条/人类观察菌24条，要求每人恰好3条）

策略（v2，post 列表接口匿名访问会返回残缺的旧列表，不可信）：
1. 新旧排序以 aweme_id 数值为准（随发布时间是单调递增的，最可靠）→ 每人留最新 3 条
2. 跳过置顶/杂帖（阿七的"分享一些短视频心得"等）
3. 逐条调 aweme/detail 接口回查真实 create_time，修正 date/time/互动数（保留 ASR 文案和拆解）
4. detail 也失败时：阿七从标题"8月X日"推断日期；其余保留原日期
"""
import json, os, sys, re, time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
WORK = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(WORK, "data.json")

SKIP_KEYWORDS = {
    "阿七大型纪录片": ["分享一些短视频心得", "短视频创业"],
}

from generate_hot import BLOGGER_SEC_UIDS  # noqa: E402


def aid_of(a):
    try:
        return int(a.get("aweme_id") or 0)
    except (TypeError, ValueError):
        return 0


def main():
    data = json.load(open(DATA, encoding="utf-8-sig"))
    articles = data["articles"]
    bloggers = [a for a in articles if a.get("source") == "blogger"]
    others = [a for a in articles if a.get("source") != "blogger"]

    # 1. 每人：剔杂帖 → aweme_id 去重 → 降序留 3
    new_bloggers = []
    names = []
    for a in bloggers:
        n = a.get("blogger_name")
        if n and n not in names:
            names.append(n)
    for name in names:
        olds = [a for a in bloggers if a.get("blogger_name") == name]
        olds = [a for a in olds
                if not any(kw in (a.get("title") or "") for kw in SKIP_KEYWORDS.get(name, []))]
        seen, uniq = set(), []
        for a in sorted(olds, key=aid_of, reverse=True):
            aid = str(a.get("aweme_id") or a.get("id"))
            if aid in seen:
                continue
            seen.add(aid)
            uniq.append(a)
        kept = uniq[:3]
        new_bloggers.extend(kept)
        print(f"  {name}: {len(olds)} → {len(kept)} 条 (aweme_id 降序)")

    # 2. detail 接口回查真实 create_time
    try:
        from douyin_dl import DouyinDL, COMMON
        dl = DouyinDL()
        ok = fail = 0
        for a in new_bloggers:
            aid = str(a.get("aweme_id") or "")
            if not aid:
                continue
            try:
                j = dl._get("/aweme/v1/web/aweme/detail/", {**COMMON, "aweme_id": aid}).json()
                d = j.get("aweme_detail") or {}
                ct = int(d.get("create_time") or 0)
                if ct:
                    a["create_time"] = ct
                    a["date"] = datetime.fromtimestamp(ct).strftime("%Y-%m-%d")
                    a["time"] = datetime.fromtimestamp(ct).strftime("%H:%M")
                    st = d.get("statistics") or {}
                    if st.get("digg_count"):
                        a["likes"] = st["digg_count"]
                    if st.get("comment_count") is not None:
                        a["comments"] = st["comment_count"]
                    ok += 1
                    print(f"    ✅ {a.get('blogger_name')} {aid[-6:]} → {a['date']} {a['time']}")
                else:
                    fail += 1
                    print(f"    ⚠️ {a.get('blogger_name')} {aid[-6:]} 无 create_time")
            except Exception as e:
                fail += 1
                print(f"    ⚠️ {a.get('blogger_name')} {aid[-6:]} detail 失败: {type(e).__name__}")
            time.sleep(1.2)  # 防风控
        print(f"  detail 回查: 成功 {ok} / 失败 {fail}")
    except Exception as e:
        print(f"  ⚠️ DouyinDL 不可用: {e}")

    # 3. 阿七兜底：从标题"8月X日"推断日期
    for a in new_bloggers:
        if a.get("blogger_name") == "阿七大型纪录片" and not a.get("create_time"):
            m = re.search(r'(\d{1,2})月(\d{1,2})日', a.get("title") or "")
            if m:
                a["date"] = f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                print(f"    🔧 阿七标题推断日期: {a['title'][:20]} → {a['date']}")

    data["articles"] = others + new_bloggers
    json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n完成：博主视频 {len(bloggers)} → {len(new_bloggers)} 条，总文章 {len(data['articles'])} 条")


if __name__ == "__main__":
    main()
