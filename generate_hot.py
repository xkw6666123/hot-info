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
from datetime import datetime

# ── 配置 ──
OUTPUT_FILE = "data.json"
SITE_NAME = "热点信息差"
SITE_DESC = "每日社会热点聚合 + 爆款视频拆解 + AI选题灵感"
TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

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
    ]

    all_articles = []
    for name, scraper in scrapers:
        try:
            result = scraper()
            all_articles.extend(result)
            print(f"  ✅ {name}: {len(result)} 条")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    # 生成灵感
    inspirations = generate_inspirations(all_articles[:15])

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
