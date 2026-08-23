# -*- coding: utf-8 -*-
"""一次性（2026-08-23）：把 8-22 本地修复成果合并进远端最新 data.json。

背景：8-22 完成的博主数据修复（置顶帖剔除/真实 create_time/每人3条）和灵感重生成
（42条，带真实新闻素材、无串味）从未推送；期间远端 CI 每3小时更新了新闻。
本脚本以远端最新 data.json 为底（保住最新新闻），只替换博主文章和灵感。

博主合并规则（每博主）：
1. 远端条目 + 本地修复条目合并，按 aweme_id 去重
2. 同 aweme_id 优先取「有 content_intro（真实ASR）+ 有 create_time」的版本
3. 剔除置顶杂帖（阿七"分享一些短视频心得"等，与 fix_blogger_data.py 同规则）
4. 按 create_time（无则 aweme_id 数值）降序留 3 条
"""
import json, re, sys

sys.stdout.reconfigure(encoding="utf-8")

REMOTE = "data.json"                 # 已 reset 到 origin/main 的最新数据
LOCAL = "_backup_0823/data.json"     # 8-22 修复后的本地数据

SKIP_KEYWORDS = {
    "阿七大型纪录片": ["分享一些短视频心得", "短视频创业"],
}


def aid_of(a):
    try:
        return int(str(a.get("aweme_id") or 0))
    except (TypeError, ValueError):
        return 0


def quality(a):
    """排序权重：有真实ASR文案 > 有create_time"""
    has_asr = 1 if (a.get("content_intro") or "").strip() and not a.get("content_intro", "").startswith("📹") else 0
    has_ct = 1 if a.get("create_time") else 0
    return has_asr, has_ct


def main():
    remote = json.load(open(REMOTE, encoding="utf-8-sig"))
    local = json.load(open(LOCAL, encoding="utf-8-sig"))

    r_bloggers = [a for a in remote["articles"] if a.get("source") == "blogger"]
    l_bloggers = [a for a in local["articles"] if a.get("source") == "blogger"]
    others = [a for a in remote["articles"] if a.get("source") != "blogger"]
    print(f"远端: {len(remote['articles'])} 文章 (博主 {len(r_bloggers)}, 灵感 {len(remote.get('inspirations', []))})")
    print(f"本地: {len(local['articles'])} 文章 (博主 {len(l_bloggers)}, 灵感 {len(local.get('inspirations', []))})")

    names = []
    for a in r_bloggers + l_bloggers:
        n = a.get("blogger_name")
        if n and n not in names:
            names.append(n)

    merged_bloggers = []
    for name in names:
        pool = [a for a in r_bloggers + l_bloggers if a.get("blogger_name") == name]
        # 剔杂帖
        pool = [a for a in pool
                if not any(kw in (a.get("title") or "") for kw in SKIP_KEYWORDS.get(name, []))]
        # 按 aweme_id 去重，同 id 优先高质量版本
        by_id = {}
        for a in pool:
            aid = str(a.get("aweme_id") or a.get("id"))
            if aid not in by_id or quality(a) > quality(by_id[aid]):
                by_id[aid] = a
        uniq = list(by_id.values())
        # 统一按 aweme_id 数值降序：它与发布时间单调递增（与 fix_blogger_data.py 同规则）。
        # 不能用 create_time 排序——远端旧条目多数没有 ct，与 epoch 秒混排量纲不一致。
        uniq.sort(key=aid_of, reverse=True)
        kept = uniq[:3]
        merged_bloggers.extend(kept)
        ids = [f"{(a.get('title') or '')[:18]}@{a.get('date')}{'(ASR)' if quality(a)[0] else ''}" for a in kept]
        print(f"  {name}: 池{len(pool)} → {len(kept)} 条 | " + " ; ".join(ids))

    remote["articles"] = others + merged_bloggers
    remote["inspirations"] = local.get("inspirations", [])

    json.dump(remote, open(REMOTE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n合并完成: {len(remote['articles'])} 文章, {len(remote['inspirations'])} 灵感")


if __name__ == "__main__":
    main()
