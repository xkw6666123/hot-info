#!/usr/bin/env python3
"""
为博主视频生成内容简介：基于同日期新闻数据 + 视频描述
策略：
1. 从 data.json 中找同日期的高热度新闻作为"当日热点"
2. 有真实文案的视频：简介=原文总结 + 当日热点
3. 日更标题类的视频：简介=当日热点列表
"""
import json
from collections import defaultdict


def find_hot_news_by_date(all_articles, date, limit=8):
    """找到指定日期的高热度新闻"""
    candidates = []
    for a in all_articles:
        if a.get("source") == "blogger":
            continue
        adate = a.get("date", "")
        if adate == date:
            title = a.get("title", "")
            likes = a.get("likes", 0) or 0
            candidates.append((likes, title))
    
    candidates.sort(key=lambda x: x[0], reverse=True)
    
    seen = set()
    result = []
    for likes, title in candidates:
        key = title[:20]
        if key not in seen:
            seen.add(key)
            result.append(title)
        if len(result) >= limit:
            break
    
    return result[:limit]


def has_real_text(title, summary):
    """判断视频是否有真实内容文案（而非仅日期标题+标签）"""
    title_only = title.split("#")[0].strip()
    summary_only = summary.split("#")[0].strip() if summary else ""
    text = summary_only if len(summary_only) > len(title_only) else title_only
    
    # 日期标题模式：如 "5月9日社会热点信息差"
    date_pattern = any([
        "月" in text[:6] and "日" in text[:8] and len(text) < 20,
        text == "放空自己。",
        text == "今日热点快报",
    ])
    
    # 有真实内容的关键词标志
    content_keywords = [
        '血赚', '退款', '崩溃', '内幕', '真相', '反转', '离谱',
        '塌房', '曝光', '震惊', '破防', '男大', '女大', '老板',
        '猫猫', '装到', '说实话', '公司', '退钱', '刚哥', '顾客',
        '新衣', '五一', '节后', '包鱼塘'
    ]
    
    has_detail = not date_pattern and (
        len(text) > 10 and any(kw in text for kw in content_keywords)
    )
    
    return has_detail, text


def generate_bullet_list(titles, max_items=5):
    """生成新闻列表"""
    if not titles:
        return ""
    return "\n".join(f"  · {t}" for t in titles[:max_items])


def generate_intro(v, all_articles):
    """基于新闻数据生成内容简介"""
    a = v.get("analysis", {})
    title = v.get("title", "")
    blogger = v.get("blogger_name", "")
    date = v.get("date", "")
    summary = v.get("summary", "")
    
    is_detail, text_content = has_real_text(title, summary)
    
    # 找到同日期新闻
    hot_news = find_hot_news_by_date(all_articles, date, limit=5)
    
    if not hot_news:
        # 找最近日期
        dates_available = sorted(set(
            a.get("date", "") for a in all_articles 
            if a.get("source") != "blogger" and a.get("date")
        ))
        for d in reversed(dates_available):
            if d <= date:
                hot_news = find_hot_news_by_date(all_articles, d, limit=5)
                if hot_news:
                    break
    
    news_text = generate_bullet_list(hot_news) if hot_news else ""
    
    # 拼接最终简介
    if is_detail:
        # 有真实文案：简述+热点
        if "网吧信息差" in blogger:
            lead = f"本期以大学生视角解读「{text_content}」。"
        elif "陈先生" in blogger:
            lead = f"本期大型纪录片风格深度解构「{text_content}」。"
        elif "信息黑板报" in blogger:
            lead = f"本期聚焦「{text_content}」。"
        elif "人类观察菌" in blogger:
            lead = f"本期迷惑行为大赏：「{text_content}」。"
        else:
            lead = f"本期内容：「{text_content}」。"
        
        if news_text:
            return f"{lead}\n\n📰 {date} 当日关联热点：\n{news_text}"
        return lead
    else:
        # 日更标题类：用热点列表做内容
        blogger_templates = {
            "阿七大型纪录片": f"📺 {date} 社会热点信息差日报，快速播报当日热搜新闻：",
            "网吧信息差": f"📺 {date} 热点搬运，从大学生视角解读当日热点：",
            "信息黑板报": f"📺 {date} 社会热点信息差合集，精选当日民生话题：",
            "人类观察菌": f"📺 {date} 人类迷惑行为大赏，精选逆天离谱新闻：",
            "陈先生": f"📺 {date} 热点深度解构，纪录片形式复盘重大事件：",
            "沙漠一之雕": f"📺 {date} B站热点快报，热搜话题搞笑合集：",
        }
        lead = blogger_templates.get(blogger, f"📺 {date} 热点视频，可能包含以下话题：")
        
        if news_text:
            return f"{lead}\n{news_text}"
        return f"{lead}\n暂无详细数据"


def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    all_articles = d["articles"]
    count = 0
    
    for a in all_articles:
        if a.get("source") != "blogger":
            continue
        
        new_intro = generate_intro(a, all_articles)
        if new_intro != a.get("content_intro", ""):
            a["content_intro"] = new_intro
            count += 1
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    
    print(f"✅ 已为 {count} 条博主视频重新生成内容简介\n")
    for a in all_articles:
        if a.get("source") == "blogger":
            intro = a["content_intro"]
            short = intro[:120].replace("\n", " ")
            print(f"[{a['blogger_name']}] {a.get('date','?')}")
            print(f"  {short}...\n")


if __name__ == "__main__":
    main()
