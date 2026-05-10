#!/usr/bin/env python3
"""
自动化热点数据采集脚本 (GitHub Actions 用)
来源: 百度/知乎/哔哩哔哩/今日头条/澎湃/华尔街见闻/财联社/凤凰/贴吧/微博/抖音
"""
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# ── 配置 ──
OUTPUT_FILE = "data.json"
SITE_NAME = "热点信息差"
SITE_DESC = "每日社会热点聚合 + 爆款视频拆解 + AI选题灵感"
TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ── TikHub 博主追踪 ──
TIKHUB_API_KEY = "srAlG/ROjGy6h0XKAoib+DTMbQKKX6Ns/SbJvkumTaW8jVOVPVyHSROeOw=="
TIKHUB_BASE = "https://api.tikhub.io"
TIKHUB_TIMEOUT = 30

# 追踪的博主列表: 填博主抖音名称即可
TRACKED_BLOGGERS = [
    "网吧信息差",
    "阿七大型纪录片",
    "陈先生",
    "信息黑板报",
    "沙漠一之雕",
]

today = datetime.now().strftime("%Y-%m-%d")
now_time = datetime.now().strftime("%H:%M")

def fetch(url, headers=None):
    """HTTP GET，返回解码后的字符串"""
    if headers is None:
        headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠️ 获取失败: {url[:60]} → {e}")
        return None

def fetch_json(url, headers=None):
    """HTTP GET，返回 JSON"""
    text = fetch(url, headers)
    if text is None:
        return None
    try:
        return json.loads(text)
    except:
        return None

def tikhub_request(endpoint, params=None):
    """调用 TikHub API"""
    url = f"{TIKHUB_BASE}{endpoint}"
    if params:
        query = urllib.parse.urlencode(params)
        url += f"?{query}"
    headers = {
        "Authorization": f"Bearer {TIKHUB_API_KEY}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIKHUB_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ⚠️ TikHub API 失败: {e}")
        return None


# ═══════════════════════════════════════════════════════
#  各平台抓取
# ═══════════════════════════════════════════════════════

def scrape_baidu():
    """百度热搜"""
    print("📡 百度热搜...")
    data = fetch_json("https://top.baidu.com/board?tab=realtime")
    if not data:
        return []
    cards = data.get("data", {}).get("cards", [])
    articles = []
    for card in cards:
        for item in card.get("content", [])[:10]:
            articles.append({
                "id": hash(f"baidu_{item.get('word','')}") % 10**9,
                "title": item.get("word", item.get("query", "")),
                "summary": item.get("desc", "")[:100],
                "source": "百度热搜",
                "date": today,
                "time": now_time,
                "tags": ["社会", "热点", "资讯"],
                "url": f"https://www.baidu.com/s?wd={item.get('word','')}",
                "likes": item.get("hotScore", 10000),
                "comments": 0,
            })
    return articles

def scrape_zhihu():
    """知乎热榜"""
    print("📡 知乎热榜...")
    data = fetch_json("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=10")
    if not data:
        return []
    articles = []
    for item in data.get("data", [])[:10]:
        target = item.get("target", {})
        articles.append({
            "id": hash(f"zhihu_{target.get('id','')}") % 10**9,
            "title": target.get("title", ""),
            "summary": target.get("excerpt", "")[:100],
            "source": "知乎",
            "date": today,
            "time": now_time,
            "tags": ["热议", "观点", "深挖"],
            "url": target.get("url", f"https://www.zhihu.com/question/{target.get('id','')}"),
            "likes": 50000,
            "comments": 500,
        })
    return articles

def scrape_bilibili():
    """B站热搜"""
    print("📡 B站热搜...")
    data = fetch_json("https://api.bilibili.com/x/web-interface/wbi/search/square?limit=10")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("trending", {}).get("list", [])[:10]:
        articles.append({
            "id": hash(f"bili_{item.get('keyword','')}") % 10**9,
            "title": item.get("keyword", item.get("show_name", "")),
            "summary": f"B站热搜: {item.get('show_name','')}",
            "source": "bilibili",
            "date": today,
            "time": now_time,
            "tags": ["年轻", "二次元", "热门"],
            "url": f"https://search.bilibili.com/all?keyword={item.get('keyword','')}",
            "likes": 30000,
            "comments": 300,
        })
    return articles

def scrape_toutiao():
    """今日头条热榜"""
    print("📡 今日头条...")
    data = fetch_json("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc")
    if not data:
        return []
    articles = []
    for item in data.get("data", [])[:10]:
        articles.append({
            "id": hash(f"toutiao_{item.get('ClusterId','')}") % 10**9,
            "title": item.get("Title", ""),
            "summary": item.get("Label", "")[:100],
            "source": "今日头条",
            "date": today,
            "time": now_time,
            "tags": ["社会", "资讯", "热议"],
            "url": f"https://www.toutiao.com/trending/{item.get('ClusterId','')}/",
            "likes": int(item.get("HotValue", 10000)),
            "comments": 100,
        })
    return articles

def scrape_thepaper():
    """澎湃新闻热榜"""
    print("📡 澎湃新闻...")
    data = fetch_json("https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("hotNews", [])[:10]:
        articles.append({
            "id": hash(f"paper_{item.get('contId','')}") % 10**9,
            "title": item.get("name", ""),
            "summary": "",
            "source": "澎湃新闻",
            "date": today,
            "time": now_time,
            "tags": ["新闻", "社会", "时政"],
            "url": f"https://www.thepaper.cn/newsDetail_forward_{item.get('contId','')}",
            "likes": 20000,
            "comments": 200,
        })
    return articles

def scrape_wallstreetcn():
    """华尔街见闻"""
    print("📡 华尔街见闻...")
    data = fetch_json("https://api-one.wallstcn.com/apiv1/content/lives?limit=10")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("items", [])[:10]:
        articles.append({
            "id": hash(f"ws_{item.get('id','')}") % 10**9,
            "title": item.get("title", ""),
            "summary": item.get("content_text", "")[:100],
            "source": "华尔街见闻",
            "date": today,
            "time": now_time,
            "tags": ["财经", "金融", "科技"],
            "url": item.get("uri", "#"),
            "likes": 15000,
            "comments": 150,
        })
    return articles

def scrape_cls():
    """财联社"""
    print("📡 财联社...")
    data = fetch_json("https://www.cls.cn/api/sw?app=CailianpressWeb&os=web&sv=8.4.6")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("roll_data", [])[:10]:
        articles.append({
            "id": hash(f"cls_{item.get('id','')}") % 10**9,
            "title": item.get("title", ""),
            "summary": item.get("brief", "")[:100],
            "source": "财联社热门",
            "date": today,
            "time": now_time,
            "tags": ["财经", "金融", "投资"],
            "url": f"https://www.cls.cn/detail/{item.get('id','')}",
            "likes": 20000,
            "comments": 200,
        })
    return articles

def scrape_ifeng():
    """凤凰网"""
    print("📡 凤凰网...")
    text = fetch("https://news.ifeng.com/")
    if not text:
        return []
    # 简陋版：从首页提取标题
    titles = re.findall(r'"title":"([^"]+)"', text)[:10]
    urls = re.findall(r'"url":"(https://[^"]+)"', text)[:10]
    articles = []
    for i, title in enumerate(titles):
        url = urls[i] if i < len(urls) else "#"
        articles.append({
            "id": hash(f"ifeng_{i}") % 10**9,
            "title": title,
            "summary": "",
            "source": "凤凰网",
            "date": today,
            "time": now_time,
            "tags": ["新闻", "国际", "时政"],
            "url": url,
            "likes": 10000,
            "comments": 100,
        })
    return articles

def scrape_tieba():
    """贴吧热搜"""
    print("📡 贴吧...")
    data = fetch_json("https://tieba.baidu.com/hottopic/browse/topicList")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("bang_topic", {}).get("topic_list", [])[:10]:
        tid = item.get("topic_id", "")
        articles.append({
            "id": hash(f"tieba_{tid}") % 10**9,
            "title": item.get("topic_name", ""),
            "summary": item.get("topic_desc", "")[:100],
            "source": "贴吧",
            "date": today,
            "time": now_time,
            "tags": ["热议", "社会", "网友"],
            "url": f"https://tieba.baidu.com/hottopic/browse/hottopic?topic_id={tid}",
            "likes": int(item.get("discuss_num", 10000)),
            "comments": int(item.get("discuss_num", 100)),
        })
    return articles

def scrape_weibo():
    """微博热搜 (HTML抓取)"""
    print("📡 微博热搜...")
    # 微博热榜页面
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": "SUB=_2AkMRK_L_f8NxqwJRmP4WyG3haYh0wgnEieKkZxRJRMxHRl-yT9kqmgntRB6OJuL3Q2LFz2Jko5w4o7B3eMUZJQoL_5PW;"
    }
    text = fetch("https://weibo.com/ajax/side/hotSearch", headers=headers)
    if not text:
        return []
    try:
        data = json.loads(text)
    except:
        return []
    articles = []
    for item in data.get("data", {}).get("realtime", [])[:10]:
        word = item.get("word", "")
        articles.append({
            "id": hash(f"weibo_{word}") % 10**9,
            "title": item.get("note", word),
            "summary": item.get("word_scheme", "")[:100],
            "source": "微博",
            "date": today,
            "time": now_time,
            "tags": ["热议", "娱乐", "社会"],
            "url": f"https://s.weibo.com/weibo?q=%23{word}%23",
            "likes": int(item.get("raw_hot", 50000)),
            "comments": 500,
        })
    return articles

def scrape_douyin():
    """抖音热榜"""
    print("📡 抖音热榜...")
    data = fetch_json("https://www.douyin.com/aweme/v1/web/hot/search/list/?detail_list=1")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("word_list", [])[:10]:
        word = item.get("word", "")
        articles.append({
            "id": hash(f"douyin_{word}") % 10**9,
            "title": item.get("word", ""),
            "summary": f"抖音热搜: {word}",
            "source": "抖音",
            "date": today,
            "time": now_time,
            "tags": ["爆款", "短视频", "热门"],
            "url": f"https://www.douyin.com/hot/{item.get('sentence_id','')}",
            "likes": int(item.get("hot_value", 100000)),
            "comments": 1000,
        })
    return articles

def scrape_bloggers():
    """通过 TikHub API 搜索博主名称，获取最新视频"""
    print("📡 博主追踪 (TikHub)...")
    if not TRACKED_BLOGGERS:
        print("  ℹ️ 未配置追踪博主，跳过")
        return []
    
    articles = []
    for name in TRACKED_BLOGGERS:
        print(f"  📹 {name}...")
        
        # 搜索博主视频（取最新1条）
        result = tikhub_request("/api/v1/douyin/app/v3/fetch_search_result", {
            "keyword": name,
            "offset": 0,
            "count": 1,
            "search_type": "video"
        })
        
        if not result or result.get("code") != 200:
            print(f"    ⚠️ 搜索失败")
            continue
        
        data_list = result.get("data", {}).get("data", [])
        if not data_list:
            print(f"    ⚠️ 未找到视频")
            continue
        
        # 取第一条视频
        video = data_list[0]
        aweme_info = video.get("aweme_info", {}) or video
        
        desc = aweme_info.get("desc", "") or video.get("desc", "")
        stats = aweme_info.get("statistics", {}) or video.get("statistics", {})
        author = aweme_info.get("author", {}) or video.get("author", {})
        aweme_id = aweme_info.get("aweme_id", "") or video.get("aweme_id", "")
        create_time = aweme_info.get("create_time", 0) or video.get("create_time", 0)
        
        if not aweme_id:
            print(f"    ⚠️ 视频ID缺失")
            continue
        
        video_date = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d") if create_time else today
        
        article = {
            "id": hash(f"blogger_{name}_{aweme_id}") % 10**9,
            "title": desc[:50] if desc else f"{name} 最新视频",
            "summary": desc[:200] if desc else "",
            "source": "blogger",
            "blogger_name": name,
            "date": video_date,
            "time": datetime.fromtimestamp(create_time).strftime("%H:%M") if create_time else now_time,
            "tags": ["博主", "爆款", "拆解"],
            "url": f"https://www.douyin.com/video/{aweme_id}",
            "likes": stats.get("digg_count", 0) or stats.get("diggCount", 0),
            "comments": stats.get("comment_count", 0) or stats.get("commentCount", 0),
        }
        articles.append(article)
        print(f"    ✅ {desc[:30]}...  👍{article['likes']:,}")
    
    return articles


# ═══════════════════════════════════════════════════════
#  创作灵感生成
# ═══════════════════════════════════════════════════════

def generate_inspirations(articles):
    """基于热点生成创作灵感"""
    templates_wangba = [
        "悬念型: 用\"难不成是真的！{hint}\"制造好奇",
        "故事型: 用\"能理解能理解 {hint}\"引发共鸣",
        "感叹型: 用\"再见！{hint}！\"制造话题",
        "盘点型: 用\"盘点{hint}的几个名场面\"",
    ]
    templates_aqi = [
        "日期型: 用\"{date}社会热点信息差\"",
        "速览型: 用\"关于{hint}的几点思考\"",
    ]
    templates_chen = [
        "大型纪录片: 用\"大型纪录片之{hint}全程高能\"",
        "独家解读: 用\"独家解读{hint}背后的商业逻辑\"",
    ]
    
    inspirations = []
    for i, a in enumerate(articles[:15]):
        hint = a["title"][:8] if len(a["title"]) > 8 else a["title"]
        source = a["source"]
        
        w_fmt = templates_wangba[i % len(templates_wangba)]
        a_fmt = templates_aqi[i % len(templates_aqi)]
        c_fmt = templates_chen[i % len(templates_chen)]
        
        inspirations.append({
            "topic": a["title"],
            "source": source,
            "wangba_style": w_fmt.format(hint=hint, date=today),
            "aqi_style": a_fmt.format(hint=hint, date=today),
            "chen_style": c_fmt.format(hint=hint, date=today),
        })
    return inspirations


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════

def main():
    print("=" * 50)
    print(f"  热点数据自动采集 - {today} {now_time}")
    print("=" * 50)
    print()

    # 并行抓取所有平台
    scrapers = [
        ("百度热搜", scrape_baidu),
        ("知乎", scrape_zhihu),
        ("B站", scrape_bilibili),
        ("今日头条", scrape_toutiao),
        ("澎湃新闻", scrape_thepaper),
        ("华尔街见闻", scrape_wallstreetcn),
        ("财联社", scrape_cls),
        ("凤凰网", scrape_ifeng),
        ("贴吧", scrape_tieba),
        ("微博", scrape_weibo),
        ("抖音", scrape_douyin),
        ("博主追踪", scrape_bloggers),
    ]

    all_articles = []
    for name, scraper in scrapers:
        try:
            result = scraper()
            all_articles.extend(result)
            print(f"  ✅ {name}: {len(result)} 条")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    # 保留已有的博主数据（含 analysis 拆解信息）
    existing_bloggers = []
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        for a in old_data.get("articles", []):
            if a.get("source") == "blogger" and a.get("analysis"):
                existing_bloggers.append(a)
        print(f"  📌 保留 {len(existing_bloggers)} 条博主分析数据")
    except:
        pass

    # 合并：新抓的博主 + 旧的博主分析数据（去重）
    new_blogger_ids = {str(a["id"]) for a in all_articles if a.get("source") == "blogger"}
    for b in existing_bloggers:
        if str(b["id"]) not in new_blogger_ids:
            all_articles.append(b)
    
    # 去重（按id）
    seen = set()
    unique_articles = []
    for a in all_articles:
        aid = str(a.get("id", ""))
        if aid and aid not in seen:
            seen.add(aid)
            unique_articles.append(a)
    all_articles = unique_articles

    # 生成灵感（优先博主内容）
    blogger_items = [a for a in all_articles if a.get("source") == "blogger"]
    other_items = [a for a in all_articles if a.get("source") != "blogger"]
    insp_sources = blogger_items[:3] + other_items[:12]
    inspirations = generate_inspirations(insp_sources[:15])

    # 构建 data.json
    output = {
        "site": {
            "name": SITE_NAME,
            "description": SITE_DESC,
        },
        "articles": all_articles,
        "inspirations": inspirations,
        "updated_at": datetime.now().isoformat(),
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 生成完成: {len(all_articles)} 条热点 + {len(inspirations)} 条灵感")
    print(f"   输出文件: {OUTPUT_FILE}")

    return len(all_articles) > 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
