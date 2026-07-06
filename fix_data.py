#!/usr/bin/env python3
"""
数据清理脚本：
1. 博主视频只保留每个博主最新3条
2. 热点新闻只保留最近3天
3. 清理过短/重复文案
4. 更新 data.json / data.js / index.html
"""
import json, os, re, time
from datetime import datetime, timedelta

WORK = r"D:\AI\hotinfo\hot-info"
DATA_FILE = os.path.join(WORK, "data.json")
JS_FILE = os.path.join(WORK, "data.js")
HTML_FILE = os.path.join(WORK, "index.html")

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def remove_duplicate_sentences(text, min_dup_len=12):
    """删除连续重复的句子（如人类观察菌的重复"这就是你们爱猫人士的素质"）"""
    if not text:
        return text
    # 按常见标点分句
    parts = re.split(r'([。！？\n])', text)
    sentences = []
    i = 0
    while i < len(parts):
        s = parts[i]
        if i + 1 < len(parts) and parts[i+1] in '。！？\n':
            s += parts[i+1]
            i += 2
        else:
            i += 1
        if s.strip():
            sentences.append(s)
    seen = set()
    clean = []
    for s in sentences:
        key = re.sub(r'\s+', '', s)
        if len(key) >= min_dup_len and key in seen:
            continue
        seen.add(key)
        clean.append(s)
    return "".join(clean)

def clean_text(text):
    if not text:
        return text
    # 去掉明显ASR错误/噪声
    text = remove_duplicate_sentences(text)
    # 去掉平台备案信息
    text = re.sub(r'(互联网宗教|药品医疗|网上有害|违法和不良|算法推荐|ICP备|公网安备|经营许可证|网络文化经营).*?(许可证|备案|举报)', '', text)
    text = re.sub(r'^\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}', '', text)
    return text.strip()

def main():
    data = load_json(DATA_FILE)
    articles = data.get("articles", [])
    today = datetime.now().date()
    news_cutoff = today - timedelta(days=3)  # 新闻保留3天
    blog_cutoff = today - timedelta(days=5)  # 博主保留5天

    blogger_groups = {}
    news = []

    for a in articles:
        if a.get("source") == "blogger":
            name = a.get("blogger_name", "未知")
            blogger_groups.setdefault(name, []).append(a)
        else:
            try:
                d = datetime.strptime((a.get("date") or "")[:10], "%Y-%m-%d").date()
                if d >= news_cutoff:
                    news.append(a)
            except Exception:
                pass

    # 限制新闻数量：每源最多保留40条，总计不超过400条
    news_by_source = {}
    for a in news:
        src = a.get("source", "其他")
        news_by_source.setdefault(src, []).append(a)
    limited_news = []
    for src, items in news_by_source.items():
        # 按热度/点赞排序，取前40
        items.sort(key=lambda x: x.get("likes", 0) or 0, reverse=True)
        limited_news.extend(items[:40])
    limited_news.sort(key=lambda x: x.get("likes", 0) or 0, reverse=True)
    limited_news = limited_news[:400]
    news = limited_news

    cleaned_bloggers = []
    for name, items in blogger_groups.items():
        # 保留较新的
        recent = []
        for a in items:
            try:
                d = datetime.strptime((a.get("date") or "")[:10], "%Y-%m-%d").date()
                if d >= blog_cutoff:
                    recent.append(a)
            except Exception:
                pass
        # 按日期+时间排序，取最新3条
        recent.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)
        kept = recent[:3]
        cleaned_bloggers.extend(kept)
        print(f"  {name}: {len(items)}条 → 保留{len(kept)}条")

    # 清理文案
    for a in cleaned_bloggers:
        ci = a.get("content_intro", "")
        if ci:
            a["content_intro"] = clean_text(ci)

    # 组装新数据
    new_articles = news + cleaned_bloggers
    # 去重按id
    seen = set()
    unique = []
    for a in new_articles:
        aid = str(a.get("id", ""))
        if aid and aid not in seen:
            seen.add(aid)
            unique.append(a)

    data["articles"] = unique
    data["updated_at"] = datetime.now().isoformat()
    save_json(DATA_FILE, data)
    print(f"\n✅ 数据清理完成: {len(articles)} → {len(unique)} 条")
    print(f"   新闻: {len(news)} 条，博主: {len(cleaned_bloggers)} 条")

if __name__ == "__main__":
    main()
