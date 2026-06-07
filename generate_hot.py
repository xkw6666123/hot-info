#!/usr/bin/env python3
"""
自动化热点数据采集脚本 (GitHub Actions 用)
来源: 百度/知乎/哔哩哔哩/今日头条/澎湃/华尔街见闻/财联社/凤凰/贴吧/微博/抖音/公众号
"""
import json
import os
import re
import sys
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# ── 配置 ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "data.json")
SITE_NAME = "热点信息差"
SITE_DESC = "每日社会热点聚合 + 爆款视频拆解 + AI选题灵感"
TIMEOUT = 10
RETRIES = 2

# 全局时间预算：在 main() 中动态设置
IMPORT_DEADLINE = 0
FAILED_PLATFORMS = []  # 记录失败的平台
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# ── TikHub 博主追踪 ──
TIKHUB_API_KEY = os.environ.get("TIKHUB_API_KEY")
if not TIKHUB_API_KEY:
    print("  ⚠️ 安全提示: TIKHUB_API_KEY 未在环境变量中设置，将通过 GitHub Secrets 注入")
TIKHUB_BASE = "https://api.tikhub.io"
TIKHUB_TIMEOUT = 30

# 追踪的博主列表: 填博主抖音名称即可；如遇重名可用 {"name": "陈先生", "user_id": "MS4wLjAB..."} 硬编码
TRACKED_BLOGGERS = [
    "网吧信息差",
    "阿七大型纪录片",
    {"name": "陈先生", "user_id": "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF"},  # chenxiansheng274 8.9万粉丝
    "人类观察菌",
]

# B站博主追踪: name + mid (UID)
BILI_BLOGGERS = [
    {"name": "沙漠一之雕", "mid": "283204224"},
]

# 抖音博主 sec_uid 映射（免费Playwright方案用）
BLOGGER_SEC_UIDS = {
    "网吧信息差": "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv",
    "阿七大型纪录片": "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf",
    "陈先生": "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF",
    "人类观察菌": "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN",
}

today = datetime.now().strftime("%Y-%m-%d")
now_time = datetime.now().strftime("%H:%M")

def refresh_time():
    """刷新时间变量（在main()开头调用，避免跨日运行日期错误）"""
    global today, now_time
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M")

# ── 确定性 ID 生成（hashlib.md5，跨运行一致）──
def make_id(prefix, seed):
    return int(hashlib.md5(f"{prefix}_{seed}".encode()).hexdigest()[:8], 16) % 10**9

def safe_int(val, default=0):
    """安全整数转换，失败返回默认值"""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

# ── 网络策略：国内平台直连，TikHub 走代理 ──
# fetch() 用直连 opener（忽略系统代理如 v2ray）
_no_proxy_handler = urllib.request.ProxyHandler({})
_no_proxy_opener = urllib.request.build_opener(_no_proxy_handler)

def fetch(url, headers=None, referer=None):
    """HTTP GET（带 3 次重试），返回解码后的字符串。强制直连，不走系统代理
    自动处理 gzip 压缩（自定义 ProxyHandler opener 不自动解压）"""
    import gzip as _gzip
    default_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/json,application/xhtml+xml,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    if referer:
        default_headers["Referer"] = referer
    if headers:
        default_headers.update(headers)
    
    last_error = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=default_headers)
            with _no_proxy_opener.open(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
                # 手动解压 gzip（自定义 opener 不自动处理）
                encoding = resp.headers.get("Content-Encoding", "")
                if "gzip" in encoding:
                    raw = _gzip.decompress(raw)
                return raw.decode("utf-8", errors="replace")
        except Exception as e:
            last_error = e
            if attempt < RETRIES - 1:
                time.sleep(1.5 * (attempt + 1))
    
    print(f"  ⚠️ 获取失败 ({RETRIES}次重试): {url[:60]} → {last_error}")
    return None

def fetch_json(url, headers=None, referer=None):
    """HTTP GET，返回 JSON"""
    text = fetch(url, headers, referer)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def tikhub_request(endpoint, params=None, method="GET"):
    """调用 TikHub API（支持 GET/POST）"""
    if not TIKHUB_API_KEY:
        print("  ⚠️ TIKHUB_API_KEY 未设置，跳过 TikHub 请求")
        return None
    url = f"{TIKHUB_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {TIKHUB_API_KEY}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json"
    }
    
    data = None
    if method == "POST" and params:
        data = json.dumps(params).encode("utf-8")
    elif params:
        query = urllib.parse.urlencode(params)
        url += f"?{query}"
    
    last_error = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(url, headers=headers, data=data, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIKHUB_TIMEOUT) as resp:
                raw = json.loads(resp.read().decode("utf-8", errors="replace"))
                # 防御：如果 API 返回字符串而非 dict，包装为 dict
                if isinstance(raw, str):
                    raw = {"code": 0, "msg": raw}
                elif not isinstance(raw, dict):
                    raw = {"code": 0, "data": raw}
                return raw
        except Exception as e:
            last_error = e
            if attempt < RETRIES - 1:
                time.sleep(2)
    
    print(f"  ⚠️ TikHub API 失败: {last_error}")
    return None


# ═══════════════════════════════════════════════════════
#  各平台抓取
# ═══════════════════════════════════════════════════════

def scrape_baidu():
    """百度热搜"""
    print("📡 百度热搜...")
    text = fetch("https://top.baidu.com/board?tab=realtime", referer="https://top.baidu.com/")
    if not text:
        return []
    # 百度把 JSON 数据嵌在 HTML comment 中
    import re
    m = re.search(r'<!--s-data:(.*?)-->', text)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    cards = data.get("data", {}).get("cards", [])
    articles = []
    for card in cards:
        for item in card.get("content", [])[:10]:
            articles.append({
                "id": make_id("baidu", item.get('word','')) % 10**9,
                "title": item.get("word", item.get("query", "")),
                "summary": item.get("desc", "")[:100],
                "source": "百度热搜",
                "date": today,
                "time": now_time,
                "tags": ["社会", "热点", "资讯"],
                "url": f"https://www.baidu.com/s?wd={item.get('word','')}",
                "likes": safe_int(item.get("hotScore"), 10000),
                "comments": 0,
            })
    return articles

def scrape_zhihu():
    """知乎热榜（guest feed API，无需登录）"""
    print("📡 知乎热榜...")
    data = fetch_json("https://www.zhihu.com/api/v3/explore/guest/feeds?limit=10",
                      referer="https://www.zhihu.com/explore")
    if not data:
        return []
    items = data.get("data", [])
    if not items:
        return []
    articles = []
    for item in items[:10]:
        target = (item.get("target") or {})
        title = ""
        url = ""
        # 从嵌套结构中提取标题
        if isinstance(target, dict):
            question = target.get("question", target)
            if isinstance(question, dict):
                title = question.get("title", "")
                qid = question.get("id", "")
                url = f"https://www.zhihu.com/question/{qid}" if qid else ""
        if not title:
            title = target.get("title", "")
        if not title:
            continue
        articles.append({
            "id": make_id("zh", title) % 10**9,
            "title": title,
            "summary": "",
            "source": "知乎", "date": today, "time": now_time,
            "tags": ["知乎", "热榜"],
            "url": url or f"https://www.zhihu.com/search?type=content&q={urllib.parse.quote(title)}",
            "likes": 50000, "comments": 100,
        })
    return articles

def scrape_bilibili():
    """B站热搜"""
    print("📡 B站热搜...")
    data = fetch_json("https://api.bilibili.com/x/web-interface/wbi/search/square?limit=10", referer="https://www.bilibili.com/")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("trending", {}).get("list", [])[:10]:
        articles.append({
            "id": make_id("bili", item.get('keyword','')) % 10**9,
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

def scrape_bilibili_bloggers():
    """B站博主追踪：搜索 UID → 获取最新视频"""
    if not BILI_BLOGGERS:
        return []
    
    print("📡 B站博主追踪...")
    articles = []
    
    for blogger in BILI_BLOGGERS:
        name = blogger["name"]
        mid = blogger.get("mid", "")
        
        # 如果没有 mid，先搜索
        if not mid:
            url = f"https://api.bilibili.com/x/web-interface/search/type?search_type=bili_user&keyword={urllib.parse.quote(name)}"
            data = fetch_json(url, referer="https://www.bilibili.com/")
            if data and data.get("code") == 0:
                users = data.get("data", {}).get("result", [])
                for u in users:
                    if isinstance(u, dict) and (u.get("uname") == name or name in u.get("uname", "")):
                        mid = str(u.get("mid", ""))
                        break
            if not mid:
                print(f"  📹 {name}: 未找到 B站 UID")
                continue
        
        # 获取最新视频（B站 space API 需要新连接，复用 opener 可能触发 412）
        print(f"  📹 {name} (mid={mid})...")
        url = f"https://api.bilibili.com/x/space/arc/search?mid={mid}&ps=5&pn=1&order=pubdate"
        
        data = None
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Referer": f"https://space.bilibili.com/{mid}",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                })
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                    code = data.get("code")
                    if code == 0:
                        break
                    elif code == -799:
                        wait = 15 * (attempt + 1)
                        print(f"    ⏳ 限流，等待{wait}s后重试({attempt+1}/5)...")
                        time.sleep(wait)
                    else:
                        time.sleep(2)
            except Exception as e:
                if attempt < 4:
                    wait = 15 * (attempt + 1)
                    print(f"    ⏳ 网络异常，等待{wait}s后重试({attempt+1}/5)...")
                    time.sleep(wait)
                else:
                    print(f"    ⚠️ 获取失败: {e}")
        
        if not data or data.get("code") != 0:
            if data:
                print(f"    ⚠️ code={data.get('code')}, msg={data.get('message','')}")
            continue
        
        vlist = data.get("data", {}).get("list", {}).get("vlist", [])
        if not vlist:
            print(f"    ⚠️ 无视频")
            continue
        
        print(f"    ✅ 找到 {len(vlist)} 条视频")
        
        for v in vlist[:3]:
            created = v.get("created", 0)
            articles.append({
                "id": make_id("bili_blogger", f"{name}_{v.get('bvid','')}") % 10**9,
                "title": v.get("title", f"{name} 最新视频")[:50],
                "summary": (v.get("description", "") or v.get("title", ""))[:200],
                "source": "blogger",
                "blogger_name": name,
                "platform": "bilibili",
                "date": datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else today,
                "time": datetime.fromtimestamp(created).strftime("%H:%M") if created else now_time,
                "tags": ["B站", "博主", "热点"],
                "url": f"https://www.bilibili.com/video/{v.get('bvid','')}",
                "likes": safe_int(v.get("favorites"), 0),
                "comments": safe_int(v.get("comment"), 0),
                "play_count": v.get("play", 0),
                "aweme_id": v.get("bvid", ""),
                "create_time": created,
            })
    
    return articles

def scrape_toutiao():
    """今日头条热榜"""
    print("📡 今日头条...")
    data = fetch_json("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc", referer="https://www.toutiao.com/")
    if not data:
        return []
    articles = []
    for item in data.get("data", [])[:10]:
        articles.append({
            "id": make_id("toutiao", item.get('ClusterId','')) % 10**9,
            "title": item.get("Title", ""),
            "summary": item.get("Abstract", item.get("Title", ""))[:100],
            "source": "今日头条",
            "date": today,
            "time": now_time,
            "tags": ["社会", "资讯", "热议"],
            "url": f"https://www.toutiao.com/trending/{item.get('ClusterId','')}/",
            "likes": safe_int(item.get("HotValue"), 10000),
            "comments": 100,
        })
    return articles

def scrape_thepaper():
    """澎湃新闻热榜"""
    print("📡 澎湃新闻...")
    data = fetch_json("https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar",
                      referer="https://www.thepaper.cn/")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("hotNews", [])[:10]:
        node_info = item.get("nodeInfo", {}) or {}
        articles.append({
            "id": make_id("paper", item.get('contId','')) % 10**9,
            "title": item.get("name", ""),
            "summary": node_info.get("desc", "")[:100],
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
    """华尔街见闻（实时快讯API，只取5条避免财经内容过多）"""
    print("📡 华尔街见闻...")
    data = fetch_json("https://api-one.wallstcn.com/apiv1/content/lives?limit=5&channel=global-channel",
                      referer="https://wallstreetcn.com/")
    if not data:
        return []
    articles = []
    seen_ids = set()
    for item in data.get("data", {}).get("items", [])[:5]:
        item_id = str(item.get('id', ''))
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        content = item.get("content", "") or item.get("title", "")
        articles.append({
            "id": make_id("ws", item_id) % 10**9,
            "title": content[:200],
            "summary": "",
            "source": "华尔街见闻",
            "date": today, "time": now_time,
            "tags": ["财经", "金融", "实时"],
            "url": f"https://wallstreetcn.com/livenews/{item_id}",
            "likes": 5000, "comments": 50,
        })
    return articles

def scrape_cls():
    """财联社（API不可用时从HTML抓取）"""
    print("📡 财联社...")
    # 尝试 API（可能已迁移）
    data = fetch_json("https://www.cls.cn/v1/roll/get_roll_list?app=CailianpressWeb&os=web&sv=8.4.6",
                      referer="https://www.cls.cn/")
    if data and data.get("data"):
        items = data.get("data", {}).get("roll_data", []) or data.get("data", [])
        if items:
            articles = []
            for item in items[:10]:
                articles.append({
                    "id": make_id("cls", str(item.get('id',''))) % 10**9,
                    "title": item.get("title", "") or item.get("content", "")[:200],
                    "summary": item.get("brief", "")[:100] if item.get("brief") else "",
                    "source": "财联社热门",
                    "date": today, "time": now_time,
                    "tags": ["财经", "金融", "投资"],
                    "url": f"https://www.cls.cn/detail/{item.get('id','')}",
                    "likes": 20000, "comments": 200,
                })
            return articles
    
    # 降级：从首页HTML提取
    print("  ⚠️ API不可用，从HTML降级抓取...")
    html = fetch("https://www.cls.cn/", referer="https://www.cls.cn/")
    if not html:
        return []
    # 匹配首页新闻标题和链接
    pattern = r'<a[^>]*href="(/detail/\d+)"[^>]*>([^<]{8,200})</a>'
    matches = re.findall(pattern, html)
    articles = []
    seen = set()
    for url, title in matches:
        title = re.sub(r'<[^>]+>', '', title).strip()
        if not title or len(title) < 8 or title in seen:
            continue
        seen.add(title)
        articles.append({
            "id": make_id("cls", url) % 10**9,
            "title": title,
            "summary": "",
            "source": "财联社热门",
            "date": today, "time": now_time,
            "tags": ["财经", "金融", "投资"],
            "url": f"https://www.cls.cn{url}" if url.startswith("/") else url,
            "likes": 20000, "comments": 200,
        })
        if len(articles) >= 10:
            break
    return articles

def scrape_ifeng():
    """凤凰网"""
    print("📡 凤凰网...")
    text = fetch("https://news.ifeng.com/")
    if not text:
        return []
    # 从首页提取新闻标题和链接
    # 匹配模式：<a href="..." title="新闻标题" 或 <a class="..." href="..." title="新闻标题"
    pattern = r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"'
    matches = re.findall(pattern, text)
    
    # 过滤掉非新闻链接（如导航栏、品牌栏目等）
    news_items = []
    for url, title in matches:
        # 跳过空标题、过短标题、导航栏标题
        if not title or len(title) < 8:
            continue
        # 跳过明显的导航栏标题
        skip_titles = ["首页", "资讯", "视频", "直播", "凤凰卫视", "财经", "娱乐", "体育", "时尚", "汽车", "房产", "科技", "军事", "文化", "旅游", "佛教", "国学", "数码", "健康", "公益", "教育", "酒业", "美食", "品牌主场", "更多>"]
        if title in skip_titles:
            continue
        # 跳过重复标题
        if title in [item["title"] for item in news_items]:
            continue
        # 处理URL
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = "https://news.ifeng.com/" + url
        
        news_items.append({"title": title, "url": url})
        if len(news_items) >= 10:
            break
    
    articles = []
    for i, item in enumerate(news_items):
        articles.append({
            "id": make_id("ifeng", i) % 10**9,
            "title": item["title"],
            "summary": "",
            "source": "凤凰网",
            "date": today,
            "time": now_time,
            "tags": ["新闻", "国际", "时政"],
            "url": item["url"],
            "likes": 10000,
            "comments": 100,
        })
    return articles

def scrape_tieba():
    """贴吧热搜"""
    print("📡 贴吧...")
    data = fetch_json("https://tieba.baidu.com/hottopic/browse/topicList", referer="https://tieba.baidu.com/")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("bang_topic", {}).get("topic_list", [])[:10]:
        tid = item.get("topic_id", "")
        articles.append({
            "id": make_id("tieba", tid) % 10**9,
            "title": item.get("topic_name", ""),
            "summary": item.get("topic_desc", "")[:100],
            "source": "贴吧",
            "date": today,
            "time": now_time,
            "tags": ["热议", "社会", "网友"],
            "url": f"https://tieba.baidu.com/hottopic/browse/hottopic?topic_id={tid}",
            "likes": safe_int(item.get("discuss_num"), 10000),
            "comments": safe_int(item.get("discuss_num"), 100),
        })
    return articles

def scrape_weibo():
    """微博热搜 (HTML抓取)"""
    print("📡 微博热搜...")
    # 微博热榜页面
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": os.environ.get("WEIBO_COOKIE", "")
    }
    if not headers["Cookie"]:
        print("  ⚠️ WEIBO_COOKIE 未设置，微博可能抓取失败，将通过 GitHub Secrets 注入")
    text = fetch("https://weibo.com/ajax/side/hotSearch", headers=headers, referer="https://weibo.com/")
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
            "id": make_id("weibo", word) % 10**9,
            "title": item.get("note", word),
            "summary": item.get("word_scheme", "")[:100],
            "source": "微博",
            "date": today,
            "time": now_time,
            "tags": ["热议", "娱乐", "社会"],
            "url": f"https://s.weibo.com/weibo?q=%23{word}%23",
            "likes": safe_int(item.get("raw_hot"), 50000),
            "comments": 500,
        })
    return articles

def scrape_douyin():
    """抖音热榜"""
    print("📡 抖音热榜...")
    data = fetch_json("https://www.douyin.com/aweme/v1/web/hot/search/list/?detail_list=1", referer="https://www.douyin.com/")
    if not data:
        return []
    articles = []
    for item in data.get("data", {}).get("word_list", []):
        word = item.get("word", "")
        articles.append({
            "id": make_id("douyin", word) % 10**9,
            "title": item.get("word", ""),
            "summary": f"抖音热搜: {word}",
            "source": "抖音",
            "date": today,
            "time": now_time,
            "tags": ["爆款", "短视频", "热门"],
            "url": f"https://www.douyin.com/hot/{item.get('sentence_id','')}",
            "likes": safe_int(item.get("hot_value"), 100000),
            "comments": 1000,
        })
    return articles

def scrape_weixin():
    """公众号热点（主API + 微博降级）"""
    print("📡 公众号热点...")
    # 主API: vvhan
    data = fetch_json("https://api.vvhan.com/api/hotlist/weixin", referer="https://api.vvhan.com/")
    if data:
        items = data.get("data", [])
        if items:
            articles = []
            for item in items[:10]:
                articles.append({
                    "id": make_id("wx", item.get("title","")) % 10**9,
                    "title": item.get("title", ""),
                    "summary": item.get("desc", "")[:100] if item.get("desc") else "",
                    "source": "公众号热点",
                    "date": today, "time": now_time,
                    "tags": ["公众号", "社会热点", "热议"],
                    "url": item.get("url", "#"),
                    "likes": safe_int(item.get("hot"), 10000),
                    "comments": 100,
                })
            return articles
    
    # API失败：用微博热搜 + 搜狗微信搜索链接，只保留社会争议性话题
    print("  ⚠️ API不可达，用微博热搜+搜狗搜索")
    wb = scrape_weibo()
    if wb:
        # 过滤娱乐/明星/广告/无争议内容，只留社会/政治/争议/财经类
        skip_words = ['表白', '520', '礼物', '新歌', '新剧', '综艺', '演唱会', '直播', 
                      '穿搭', '发型', '妆容', '减肥', '健身', '美食', '旅游', '星座',
                      '磕糖', 'CP', '同框', '发箍', '下班', '剧组', '海报', '预告',
                      '淘宝', '折扣', '红包', '代言', '广告', '上映', '定档']
        keep_words = ['特朗普', '访华', '中美', '习近平', '国务院', '外交部', '国台办',
                      'A股', '芯片', '存储', '涨价', '银行', '房贷', '房价', '政策',
                      '法院', '刑拘', '偷拍', '猥亵', '强奸', '杀人', '死亡', '事故',
                      '爆炸', '火灾', '地震', '台风', '高温', '暴雨', '洪水',
                      '争议', '举报', '投诉', '维权', '霸王', '离职', '辞职',
                      '收费', '涨价', '取消', '禁止', '限制', '新规',
                      '曝光', '黑幕', '回应', '道歉', '警方', '公安', '司机',
                      '留学生', '国际', '美国', '日本', '欧洲', '中东',
                      '科技', 'AI', '人工智能', '大模型', '芯片', '新机']
        
        result = []
        for a in wb:
            title = a.get("title", "")
            # 跳过低质量内容
            if any(w in title for w in skip_words):
                continue
            # 优先保留社会类
            result.append(a)
        
        # 如果没有足够社会类，补几个高质量的
        if len(result) < 8:
            for a in wb:
                if a not in result:
                    result.append(a)
                    if len(result) >= 10:
                        break
        
        result = result[:10]
        for a in result:
            a["source"] = "公众号热点"
            a["id"] = make_id("wx_fb", a["title"]) % 10**9
            a["url"] = "https://weixin.sogou.com/weixin?type=2&query=" + urllib.parse.quote(a["title"].split("#")[0])
        return result
    return []

class BlogSearcher:
    """搜索博主 + 获取最新视频的辅助类"""
    def __init__(self, name, user_id=""):
        self.name = name
        self.user_id = user_id  # 如果提供，跳过搜索直接使用
        self.results = []
    
    def run(self):
        # 步骤1：搜索用户，获取 user_id（如果已提供则跳过）
        if self.user_id:
            print(f"    🔒 使用硬编码 user_id: {self.user_id[:20]}...")
        else:
            self.user_id = self._search_user()
        
        if not self.user_id:
            return
        
        # 步骤2：获取用户作品列表（最多5条）
        posts = self._get_user_posts(self.user_id, count=5)
        if not posts:
            return
        
        # 步骤3：取最近 3 条
        for v in posts[:3]:
            parsed = self._parse_video(v)
            if parsed:
                self.results.append(parsed)
    
    def _search_user(self):
        """搜索用户，返回 (user_id, 匹配得分)"""
        # TikHub v2 搜索 API（POST）
        result = tikhub_request(
            "/api/v1/douyin/search/fetch_user_search_v2",
            {"keyword": self.name, "cursor": 0},
            method="POST"
        )
        if result and result.get("code") == 200:
            inner = result.get("data", {})
            if isinstance(inner, dict):
                users = inner.get("data", {})
                user_list = users.get("user_list", []) if isinstance(users, dict) else []
                
                # 对搜索结果排序：精确匹配优先，粉丝数高的优先
                candidates = []
                for u in user_list:
                    if not isinstance(u, dict):
                        continue
                    nick = u.get("nick_name", "")
                    uid = u.get("user_id", "")
                    if not uid:
                        continue
                    
                    # 计算匹配得分
                    score = 0
                    if nick == self.name:
                        score = 100  # 精确匹配
                    elif self.name in nick:
                        # 名字被包含在内，扣分取决于额外字符长度
                        extra = len(nick) - len(self.name)
                        score = max(80 - extra * 2, 50)
                    
                    if score >= 50:
                        followers = u.get("follower_count", 0) or 0
                        candidates.append((score, followers, uid, nick))
                
                if candidates:
                    # 高分优先，同分粉丝多优先
                    candidates.sort(key=lambda x: (-x[0], -x[1]))
                    best_score, followers, uid, matched_nick = candidates[0]
                    
                    # 如果最佳匹配得分 < 90 且名字很短（容易误匹配），打印警告
                    if best_score < 90 and len(self.name) <= 3:
                        print(f"    ⚠️ 模糊匹配: 搜索'{self.name}' → '{matched_nick}' (得分:{best_score}, 粉丝:{followers})")
                    return uid
        
        return None
    
    def _get_user_posts(self, user_id, count=5):
        """获取用户作品列表（GET 方法）"""
        result = tikhub_request(
            "/api/v1/douyin/app/v3/fetch_user_post_videos",
            {"sec_user_id": user_id, "max_cursor": 0, "count": count},
            method="GET"
        )
        if result and result.get("code") == 200:
            data = result.get("data", {})
            if isinstance(data, dict):
                aweme_list = data.get("aweme_list") or data.get("data") or []
            else:
                aweme_list = []
            return aweme_list
        return None
    
    def _parse_video(self, v):
        if not isinstance(v, dict):
            return None
        desc = v.get("desc", "")
        stats = v.get("statistics", {}) or {}
        create_time = v.get("create_time", 0)
        return {
            "aweme_id": v.get("aweme_id", ""),
            "desc": desc,
            "date": datetime.fromtimestamp(create_time).strftime("%Y-%m-%d") if create_time else today,
            "time": datetime.fromtimestamp(create_time).strftime("%H:%M") if create_time else now_time,
            "likes": safe_int(stats.get("digg_count", stats.get("diggCount")), 0),
            "comments": safe_int(stats.get("comment_count", stats.get("commentCount")), 0),
            "create_time": create_time,
        }



def _build_pw_article(name, v):
    """从PW脚本返回的视频数据构建文章条目"""
    import re
    aweme_id = v.get("id", "")
    title_text = v.get("title", "").strip()
    likes = v.get("likes", 0) or 0
    if not likes:
        m = re.match(r'([\d.]+)万', title_text)
        if m:
            likes = int(float(m.group(1)) * 10000)
            title_text = title_text[m.end():].strip()
    if not title_text:
        title_text = f"{name} 最新视频"
    return {
        "id": make_id("pw_blogger", f"{name}_{aweme_id}") % 10**9,
        "title": title_text[:80],
        "summary": f"{name}：{title_text}"[:200],
        "source": "blogger",
        "blogger_name": name,
        "date": today, "time": now_time,
        "tags": ["博主", "爆款", "拆解"],
        "url": f"https://www.douyin.com/video/{aweme_id}",
        "likes": likes,
        "comments": max(likes // 100, 10),
        "aweme_id": aweme_id,
        "content_intro": f"📹 {name}最新视频：{title_text}"[:200],
    }

def scrape_bloggers_f2():
    """使用 F2 库 + Chrome Cookie 抓取抖音博主视频（免登录API替代方案）"""
    try:
        import asyncio, browser_cookie3
        from f2.apps.douyin.handler import DouyinHandler
    except ImportError:
        print("    ⚠️ F2/browser_cookie3 未安装，跳过")
        return []
    
    # 从Chrome提取抖音cookie
    try:
        cj = browser_cookie3.chrome(domain_name='douyin.com')
        cookie_str = '; '.join(f'{c.name}={c.value}' for c in cj if 'douyin' in c.domain)
        if not cookie_str:
            print("    ⚠️ 未找到Chrome抖音cookie，请先登录网页版抖音")
            return []
    except Exception as e:
        print(f"    ⚠️ 读取Chrome cookie失败: {e}")
        return []
    
    kwargs = {
        'headers': {
            'User-Agent': USER_AGENT,
            'Referer': 'https://www.douyin.com/',
        },
        'proxies': {'http://': None, 'https://': None},
        'timeout': 10,
        'cookie': cookie_str,
    }
    
    articles = []
    
    async def _fetch():
        nonlocal articles
        for entry in TRACKED_BLOGGERS:
            name = entry["name"] if isinstance(entry, dict) else entry
            sec_uid = BLOGGER_SEC_UIDS.get(name, "")
            if not sec_uid:
                continue
            
            print(f"  📹 F2: {name}...")
            try:
                async for data in DouyinHandler(kwargs).fetch_user_post_videos(sec_uid, 0, 0, 5, 5):
                    raw = data._to_raw()
                    aweme_list = raw.get('aweme_list', [])
                    print(f"    ✅ {len(aweme_list)}条")
                    for v in aweme_list:
                        desc = (v.get('desc') or '').strip()
                        stats = v.get('statistics', {}) or {}
                        aweme_id = str(v.get('aweme_id', ''))
                        digg = stats.get('digg_count', 0) or 0
                        comment = stats.get('comment_count', 0) or 0
                        share = stats.get('share_count', 0) or 0
                        
                        # 发布时间：F2 返回的时间戳格式非标准Unix（use today as safe fallback）
                        ts = v.get('create_time', 0) or 0
                        pub_date = today
                        pub_time = now_time
                        
                        # 构建丰富的 content_intro
                        intro_parts = [desc]
                        if digg > 0:
                            intro_parts.append(f"👍 {digg//10000}万赞" if digg >= 10000 else f"👍 {digg}赞")
                        if comment > 0:
                            intro_parts.append(f"💬 {comment}评论")
                        if share > 0:
                            intro_parts.append(f"🔄 {share//10000}万分享" if share >= 10000 else f"🔄 {share}分享")
                        
                        articles.append({
                            "id": make_id("f2", f"{name}_{aweme_id}") % 10**9,
                            "title": desc[:80] if desc else f"{name} 最新视频",
                            "summary": desc[:200],
                            "source": "blogger",
                            "blogger_name": name,
                            "date": pub_date, "time": pub_time,
                            "tags": ["博主", "爆款", "拆解"],
                            "url": f"https://www.douyin.com/video/{aweme_id}",
                            "likes": digg,
                            "comments": comment,
                            "aweme_id": aweme_id,
                            "create_time": ts,
                            "content_intro": "\n".join(intro_parts)[:300],
                        })
            except Exception as e:
                print(f"    ⚠️ F2失败: {e}")
    
    # 运行异步抓取（容错：任何异常都返回已获取的部分数据）
    import asyncio as _asyncio
    try:
        loop = _asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        _asyncio.run(_fetch())
    except Exception as e:
        print(f"    ⚠️ F2运行异常(返回已获取的{len(articles)}条): {e}")
    
    return articles


def scrape_bloggers_pw():
    """Playwright 回退方案：F2 失败时使用
    优先用 v2 单会话批量抓取，降级到 v1 逐条抓取
    """
    import subprocess as _sp
    
    # 检测 bash 是否可用
    try:
        r = _sp.run(["bash", "--version"], capture_output=True, timeout=5)
        if r.returncode != 0:
            return []
    except Exception:
        return []
    
    # 找到 playwright-cli 路径（bash 子进程需要无扩展名的 shell 版本）
    import shutil as _shutil
    _pw_cli = _shutil.which("playwright-cli") or "playwright-cli"
    # Windows: shutil.which 可能返回 .CMD 版本，bash 用不了
    # 优先从 node 全局 bin 目录查找无扩展名版本
    _try_paths = [
        os.path.expanduser("~/.workbuddy/binaries/node/versions/22.12.0/playwright-cli"),
        "/usr/local/bin/playwright-cli",
    ]
    for _p in _try_paths:
        if os.path.isfile(_p):
            _pw_cli = _p
            break
    
    scrape_script_v2 = os.path.join(BASE_DIR, "pw_scrape_blogger_v2.sh")
    scrape_script_v1 = os.path.join(BASE_DIR, "pw_scrape_blogger.sh")
    if not os.path.exists(scrape_script_v1):
        return []
    
    articles = []
    _env = os.environ.copy()
    _env["PLAYWRIGHT_CLI"] = _pw_cli
    
    # 收集需要抓取的博主
    blogger_list = []
    for entry in TRACKED_BLOGGERS:
        name = entry["name"] if isinstance(entry, dict) else entry
        sec_uid = BLOGGER_SEC_UIDS.get(name, "")
        if sec_uid:
            blogger_list.append((name, sec_uid))
    
    if not blogger_list:
        return []
    
    import re as _re
    use_v2 = os.path.exists(scrape_script_v2)
    
    if use_v2:
        print(f"  📹 PW批量: {len(blogger_list)}位博主（单会话防限流）...")
        args = ["bash", scrape_script_v2]
        for n, u in blogger_list:
            args.extend([n, u])
        try:
            r = _sp.run(args, capture_output=True, text=True, timeout=360,
                       encoding="utf-8", errors="replace", env=_env)
            output = r.stdout
            if "验证码拦截" in output or "验证码" in r.stderr:
                print("    ⚠️ 验证码拦截，降级v1...")
            else:
                json_match = _re.search(r'\{.*\}', output, _re.DOTALL)
                if json_match:
                    try:
                        results = json.loads(json_match.group(0))
                        for name, videos in results.items():
                            if isinstance(videos, list) and len(videos) > 0:
                                print(f"    ✅ {name}: {len(videos)}条")
                                for v in videos[:5]:
                                    articles.append(_build_pw_article(name, v))
                        if articles:
                            return articles
                    except json.JSONDecodeError:
                        print("    ⚠️ v2 JSON解析失败，降级v1...")
        except Exception as e:
            print(f"    ⚠️ v2失败: {e}，降级v1...")
    
    # v1 降级
    for name, sec_uid in blogger_list:
        print(f"  📹 PW: {name}...")
        try:
            r = _sp.run(["bash", scrape_script_v1, name, sec_uid],
                       capture_output=True, text=True, timeout=90,
                       encoding="utf-8", errors="replace", env=_env)
            output = r.stdout
            if "验证码" in output:
                continue
            m = _re.search(r'\[.*?\]', output, _re.DOTALL)
            if not m:
                continue
            json_str = m.group(0).replace('\\"', '"')
            videos = json.loads(json_str)
            for v in videos[:5]:
                articles.append(_build_pw_article(name, v))
            print(f"    ✅ {len(videos)}条")
        except Exception as e:
            print(f"    ⚠️ PW失败: {e}")
    
    return articles


def scrape_bloggers():
    """通过 TikHub API 获取博主最新 3 条视频"""
    print("📡 博主追踪 (TikHub)...")
    if not TRACKED_BLOGGERS:
        print("  ℹ️ 未配置追踪博主，跳过")
        return []
    
    articles = []
    for entry in TRACKED_BLOGGERS:
        if isinstance(entry, dict):
            name = entry.get("name", "")
            user_id = entry.get("user_id", "")
        else:
            name = entry
            user_id = ""
        
        print(f"  📹 {name}...")
        
        searcher = BlogSearcher(name, user_id=user_id)
        searcher.run()
        
        for video in searcher.results:
            article = {
                "id": make_id("blogger", f"{name}_{video['aweme_id']}") % 10**9,
                "title": video["desc"][:50] if video["desc"] else f"{name} 最新视频",
                "summary": video["desc"][:200] if video["desc"] else "",
                "source": "blogger",
                "blogger_name": name,
                "date": video["date"],
                "time": video["time"],
                "tags": ["博主", "爆款", "拆解"],
                "url": f"https://www.douyin.com/video/{video['aweme_id']}",
                "likes": video["likes"],
                "comments": video["comments"],
            }
            articles.append(article)
        
        if searcher.results:
            print(f"    ✅ 找到 {len(searcher.results)} 条视频")
        else:
            print(f"    ⚠️ 未找到，将保留已有数据")
    
    return articles


def generate_blogger_analysis(article):
    """为博主视频自动生成analysis（基于标题和描述的规则匹配）"""
    title = (article.get("title") or "").lower()
    desc = (article.get("content_intro") or article.get("summary") or "").lower()
    blogger = article.get("blogger_name", "")
    
    # 关键词提取
    keywords = []
    hot_words = ["热点", "信息差", "社会", "新闻", "爆料", "离谱", "逆天", "迷惑", "搞笑", "玩梗", 
                 "大学生", "打工人", "职场", "恋爱", "婚姻", "教育", "医疗", "房价", "就业", "科技"]
    for w in hot_words:
        if w in title or w in desc:
            keywords.append(w)
    
    # 视频类型判断
    video_type = "社会热点信息快报"
    if any(w in title for w in ["合集", "盘点", "top", "排名"]):
        video_type = "热点合集盘点"
    elif any(w in title for w in ["搞笑", "沙雕", "离谱", "迷惑"]):
        video_type = "搞笑/沙雕向"
    elif any(w in title for w in ["教程", "教学", "怎么做"]):
        video_type = "教程/干货向"
    elif any(w in title for w in ["测评", "评测", "体验"]):
        video_type = "测评/体验向"
    
    # 封面风格判断
    cover_style = "新闻截图+醒目标签"
    if "搞笑" in title or "沙雕" in title:
        cover_style = "表情包/搞笑截图"
    elif "教程" in title:
        cover_style = "步骤图+大字标题"
    
    # 发布规律判断
    publish_pattern = "日更"
    if "周" in title or "weekly" in title.lower():
        publish_pattern = "周更"
    elif "月" in title:
        publish_pattern = "月更"
    
    # 可复制建议
    replicable_tip = f"精选今日热门{keywords[0] if keywords else '社会'}新闻做合集，标题用#{'#'.join(keywords[:3])}标签引流"
    
    return {
        "video_type": video_type,
        "cover_style": cover_style,
        "publish_pattern": publish_pattern,
        "keywords": keywords[:5] if keywords else ["热点", "社会"],
        "replicable_tip": replicable_tip,
    }


# ═══════════════════════════════════════════════════════
#  创作灵感生成
# ═══════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════
#  创作灵感生成
# ═══════════════════════════════════════════════════════

def douyin_score(a):
    """评估一篇文章在抖音的爆火潜力，返回 0-100 的分数"""
    score = 0
    title = a.get("title", "")
    likes = a.get("likes", 0) or 0
    comments = a.get("comments", 0) or 0
    source = a.get("source", "")
    tags = a.get("tags", []) or []

    # 1. 热度分（对数尺度，防止极端值主导）
    import math
    if likes > 0:
        score += min(35, math.log2(likes + 1) * 2)
    if comments > 0:
        score += min(25, math.log2(comments + 1) * 1.8)

    # 2. 情绪冲击分（标题含强情绪词 = 更容易在抖音传播）
    emotional_words = ['泪崩', '震惊', '怒了', '崩溃', '炸裂', '反转', '意外', '惊人',
                      '离谱', '逆天', '离谱', '破防', '沉默', '不敢相信', '谁都没想到']
    for w in emotional_words:
        if w in title:
            score += 12
            break

    # 3. 争议性分（争议/对立话题在抖音天然有流量）
    controversy_keywords = ['回应', '道歉', '曝光', '争议', '投诉', '维权', '实名举报',
                           '偷税', '造假', '道歉信', '通报', '声明', '发酵']
    for w in controversy_keywords:
        if w in title:
            score += 10
            break

    # 4. 标题短小精悍（<20字更适合抖音）
    clean_title = re.sub(r'\[.*?\]|#\S+', '', title).strip()
    if len(clean_title) <= 12:
        score += 10
    elif len(clean_title) <= 20:
        score += 6

    # 5. 话题类型分（娱乐/社会/奇闻在抖音天然流量 > 财经/科技）
    entertainment_tags = {'娱乐', '搞笑', '奇闻', '八卦', '明星', '综艺', '网红'}
    social_tags = {'社会', '争议', '热议', '热点', '爆款'}
    if tags and (set(tags) & entertainment_tags):
        score += 8
    elif tags and (set(tags) & social_tags):
        score += 5

    # 6. 平台分（某些平台的热搜天然更"抖音化"）
    source_boost = {'百度热搜': 8, '微博': 7, '知乎': 6, 'bilibili': 6,
                   '今日头条': 5, '贴吧': 5, '公众号热点': 3}
    score += source_boost.get(source, 2)

    # 7. 博主内容保底（博主最新视频至少给一些分数）
    if source == "blogger":
        score += 15

    return score


def generate_inspirations(all_articles):
    """从全量热点中按抖音爆火潜力选50条，生成各博主风格的完整创作草稿"""

    # ── 内部评分和筛选 ──
    # 直接使用本文件的 douyin_score 函数
    _ds = douyin_score

    # 分离博主和非博主
    blogger_items = [a for a in all_articles if a.get("source") == "blogger"]
    other_items = [a for a in all_articles if a.get("source") != "blogger"]

    # 非博主内容按评分排序
    other_items.sort(key=_ds, reverse=True)

    # 来源多样性：每源最多8条
    diverse = []
    seen_sources = {}
    for a in other_items:
        src = a.get("source", "其他")
        n = seen_sources.get(src, 0)
        if n < 8:
            diverse.append(a)
            seen_sources[src] = n + 1
        if len(diverse) >= 47:
            break

    # 合并：优先博主内容（最多3条）
    selected = blogger_items[:3] + diverse[:47]

    # ── 标题预处理 ──
    def prep(t):
        t = re.sub(r'\[.*?\]', '', t)
        t = re.sub(r'#\S+', '', t)
        return t.strip()

    def keyword(t, n=12):
        t = prep(t)
        for sep in '，。！？；、:： ':
            idx = t.find(sep)
            if 3 <= idx <= 15:
                return t[:idx]
        if len(t) <= 6:
            return t
        return t[:n]

    def short(t, n=30):
        t = prep(t)
        if len(t) <= n:
            return t
        for sep in '，。！？；、:： ':
            idx = t[:n].rfind(sep)
            if idx > n//2:
                return t[:idx]
        return t[:n]

    def ctx(t, s, blogger_name=""):
        """上下文包装：短标题用博主名或引号丰富"""
        t = prep(t)
        if len(t) < 8:
            if blogger_name:
                return f"{blogger_name}的{t}"
            return f"「{t}」这条视频"
        return t

    def pick(patterns, seed):
        return patterns[abs(hash(seed)) % len(patterns)]

    today_str = datetime.now().strftime("%m月%d日")

    # ═══════════════════════════════════════════════════
    #  网吧信息差：大学生荒诞解构 + 开篇/收尾/提示
    # ═══════════════════════════════════════════════════

    def wangba_style(topic, source, title, idx=0):
        """网吧信息差真实风格 — 标题即内容：极短(5-15字)悬念标题 + 固定标签"""
        clean = prep(topic)[:20]
        kw = keyword(topic)[:8]
        patterns = [
            f"标题：{clean if len(clean)<=15 else kw}，这合理吗？\n标签：#青年创作者成长计划 #内容过于真实 #大学生 #热点",
            f"标题：不是，{kw}？\n标签：#青年创作者成长计划 #内容过于真实 #大学生 #热点",
            f"标题：{kw} 居然是真的\n标签：#青年创作者成长计划 #内容过于真实 #大学生 #热点 #万万没想到",
            f"标题：能理解 能理解 {kw}\n标签：#青年创作者成长计划 #内容过于真实 #大学生",
            f"标题：谁还记得{kw}？\n标签：#青年创作者成长计划 #内容过于真实 #大学生 #热点",
        ]
        return pick(patterns, topic + 'wb_r8' + str(idx))

    def aqi_style(topic, source, title, idx=0):
        """阿七纪录片 — 信息差视角，逐条分析，像在看一个调查记者写稿"""
        k = keyword(topic)[:15]; s = short(topic, 40); ts = today_str
        patterns = [
            f"{ts}社会热点信息差。今天先讲一个很多人只看了一眼标题就划走的事：{s}。你可能觉得这跟你没什么关系，但巴沙帮你理了三条线：一是这件事的时间线其实比报道里说的要早将近一周；二是当事人的回应方式本身就很有意思，你仔细读他说的每一句话；三是这件事背后涉及的人群比表面上多得多。这就是信息差——你看的是新闻，别人看的是信号。",
            f"热点信息差。{s}——这条新闻今天在全网刷到的人应该不少，但是你有没有注意到，不同平台在讲同一件事的时候，侧重点完全不一样？微博在强调情绪，知乎在分析逻辑，评论区的大哥在科普背景。巴沙花了半天把这些版本都看了一遍，发现每个版本都只说了一半的事实。另一半在哪里？在这条视频里。",
            f"{ts}，巴沙今天想讲一个其实挺重要但没什么人深聊的事：{k}。这类新闻有一个共同特点——标题很平淡，点进去才发现水很深。我分三个角度帮你看：时间、人物、潜在影响。第一个角度——第二个角度——第三个——好了，信息给你了。每天一条信息差，你就比99%的人多知道一点。",
            f"为什么{s}？因为大部分人都被标题带偏了。巴沙翻了一上午原始资料，发现最早的消息源其实不是你们看到的那个账号，而是一个几乎没人关注的小号。然后这条信息经过了三次转手，每转一次就变一次意思，到了热搜上的时候已经面目全非。这个过程本身就是一个经典的信息差案例。",
            f"今天全网都在讨论{s}，但没几个人把关键节点说清楚。巴沙直接给你画时间线：第一阶段——第二阶段——反转点——现状——。你把这个时间线记住，下次再有人跟你聊这个事，你就不会被带节奏了。记住巴沙一句话：看新闻永远要看谁在说、对谁说、为什么这时候说。",
        ]
        return pick(patterns, topic + 'aqi_v7' + str(idx))

    def chen_style(topic, source, title, idx=0):
        """陈先生 — 商业纪录片风格，叙事宏大，自带BGM感"""
        k = keyword(topic)[:15]; s = short(topic, 35)
        ib = any(w in topic for w in ['上市','降价','新品','发布','收购','手机','车','股','芯片','AI','裁员','融资'])
        if ib:
            patterns = [
                f"大型纪录片之《{k}》持续为您播出。{s}，这件事如果放在三年前，没有人会信。但现在它真实地发生了。不是因为运气好，是因为整个行业走到了一个拐点。以前大家想的是怎么做大，现在所有人都在想怎么活下去。活下去的办法就一条——把东西做好，把价格打下来。不玩虚的。",
                f"这波真的不讲武德。{s}。我理解为什么很多人说不可能——因为按照常规思路这件事确实不可能。但是这次人家走的路跟你想象的不太一样。过去大家挤在一条赛道上卷，卷到最后谁都赚不到钱。现在有人换了一条路——不是更好，是更对。数据不会骗人，你自己去看。",
                f"来讲一个正在发生的产业变革：{s}。很多人看新闻只看标题，但其实这条新闻背后有三个信号：第一，产业链上游在重构；第二，终端定价逻辑在变；第三，消费者的预期被重新教育了。任何一个信号单独看都不算什么，三个信号一起出现——这就不是偶然了。",
            ]
        else:
            patterns = [
                f"大型纪录片之《{k}》。{s}，讲真的，这个事发生的时候我一点都不意外。因为在过去的三个月里，类似的事情已经有四五起了。大家觉得这是小概率事件，其实完全不是——只是以前没人统计罢了。现在统计出来了，数字摆在那里，不信也得信。这就是我说的——大数据时代，没有秘密。",
                f"今天讲一个现象级的新闻：{s}。我翻了一下评论区，点赞最高的三条评论分别代表了三种完全不同的立场。有意思的不是他们说了什么，而是他们的点赞数——你会发现这场争论其实没有赢家，每个人的观点都被一半的人支持、一半的人反对。这种撕裂感，在最近的热搜里越来越常见了。",
                f"《{k}》这部纪录片更新了。{s}。说大不大说小不小，但我注意到的不是事情本身，是各方的反应。甲方说——乙方回应——第三方插了一句——你看出来了吗？这里面有一个很微妙的权力结构。这是真实的中国互联网，比任何剧本都精彩。",
            ]
        return pick(patterns, topic + 'chen_v7' + str(idx))

    def guancha_style(topic, source, title, idx=0):
        """人类观察菌 — 冷静观察者，摆事实不讲道理，像在看一份社会实验报告"""
        k = keyword(topic)[:15]; s = short(topic, 40)
        patterns = [
            f"今日热点快报：{k}。先说基本事实——{s}，这是目前可以确认的。然后有意思的部分来了：官方说的是A，当事人说的是B，网友说的是C。三个版本，三个世界。巴沙不告诉你谁对谁错，我把所有能找到的公开信息放在下面，你自己比对，自己判断。",
            f"一条热乎的新闻：{s}。根据目前已经公开的信息，我整理了这样一个时间线——最开始是——然后是——转折出现在——现在的状态是——。你看完这条时间线，有没有觉得哪里不对劲？如果有，评论区告诉我你注意到的是什么。",
            f"热点快报，先看数据：{s}。说一下我注意到的三个细节，其他报道基本都只提了第一个。细节一——细节二——细节三——。这三个细节连起来，指向一个不太一样的方向。今天我不给结论，只呈现信息，结论交给你。",
            f"今天观察到一个有趣的现象：{k}。{s}。我打开微博评论区看了前五十条——大概60%的人说——30%的人说——剩下10%在问今天午饭吃什么。这个比例本身就是一个信号。你觉得这个比例说明了什么？来评论区聊聊你的分析。",
            f"快报时间。{s}。巴沙收集了公开信息整理了一下前后脉络：起因→发展→各方回应→最新进展。好了打出来给你们了。我今天不想评价，因为我觉得这件事的答案不在任何一方的说法里，在那些还没被说出来的信息里。评论区聊聊你的视角。",
        ]
        return pick(patterns, topic + 'gc_v7' + str(idx))

    def shadi_style(topic, source, title, idx=0):
        """沙漠一之雕 — 快节奏连播，信息量大，像在报新闻联播"""
        k = keyword(topic)[:12]; s = short(topic, 45); ts = today_str
        patterns = [
            f"一夜之间发生了啥？{ts}热点快报。第一条——{s}。起因很简单，但后面发生的事完全出乎意料。事情是这样的：最早是——结果没过多久——然后今天上午——。大家现在最关心的问题是——这个问题的答案可能比你想的复杂。来评论区一人一句。",
            f"{ts}热点开唠。昨天晚上到今天全网最热闹的新闻：{k}。给还没看的朋友用一句话说清楚——{s}。如果你觉得这件事就是一个简单的A导致B，那可能要重新想想了。因为它后面的逻辑其实是一条链：从A到B到C到D，中间每个环节都有人在操作。这不是一个人的事，是一群人的事。",
            f"用两分钟给你补完今天的热搜，先说最火的一个：{k}。{s}。目前我看到的最新情况是这样——但是如果你往回翻翻时间线，你会发现事情在三天前就已经有苗头了。为什么三天前没人关注？因为那时候信息还太碎，没人拼起来。巴沙今天帮你拼好了。",
            f"来，今天的热点按时间串一下：{s}。早上——下午——傍晚——。一天之内，事情变了三回。每回都不一样。你如果只看中午的报道，你会得出一个完全相反的结论。这就是为什么你需要信息差——不是比别人快，是比别人全。",
            f"补一下今天的热搜。{s}。先说结论：这件事现在还在发酵中，后面的走向还没定。但是有几点是确定的——第一——第二——第三——。这三点不管后面怎么变，都不会变。因为这是事实，不是观点。好，下一条——",
        ]
        return pick(patterns, topic + 'sd_v7' + str(idx))

    inspirations = []
    for i, a in enumerate(selected[:50]):
        topic = a.get("title", "")
        if not topic:
            continue
        source = a.get("source", "")
        blogger_name = a.get("blogger_name", "")
        seed = f"{topic}_{source}_{i}"
        inspirations.append({
            "topic": topic,
            "source": source,
            "blogger_name": blogger_name,
            "wangba": wangba_style(topic, source, topic, i),
            "aqi": aqi_style(topic, source, topic, i),
            "chen": chen_style(topic, source, topic, i),
            "guancha": guancha_style(topic, source, topic, i),
            "shadi": shadi_style(topic, source, topic, i),
        })
    return inspirations


def main(mode="full"):
    """
    mode: "full"=全部爬虫, "local"=跳过TikHub/B站博主, "remote"=只跑TikHub/B站+合并已有数据
    """
    global IMPORT_DEADLINE
    IMPORT_DEADLINE = time.time() + 600  # 10分钟预算，给博主爬虫留足时间
    refresh_time()  # 刷新时间，避免跨日运行日期错误
    print("=" * 50)
    print(f"  热点数据自动采集 - {today} {now_time} [{mode}]")
    print("=" * 50)
    print()

    # 并行抓取所有平台
    scrapers = [
        ("百度热搜", scrape_baidu),
        ("知乎", scrape_zhihu),
        ("B站博主", scrape_bilibili_bloggers),
        ("B站", scrape_bilibili),
        ("今日头条", scrape_toutiao),
        ("澎湃新闻", scrape_thepaper),
        ("华尔街见闻", scrape_wallstreetcn),
        ("财联社", scrape_cls),
        ("凤凰网", scrape_ifeng),
        ("贴吧", scrape_tieba),
        ("微博", scrape_weibo),
        ("抖音", scrape_douyin),
        ("公众号", scrape_weixin),
        ("博主追踪", lambda: scrape_bloggers_f2() or scrape_bloggers() or scrape_bloggers_pw()),
    ]
    
    if mode == "local":
        # local 模式：抖音API国内直连可用（已验证2026-06-07）
        pass
    elif mode == "remote":
        # 只跑海外爬虫，并合并已有 data.json
        scrapers = [(n, s) for n, s in scrapers if n in ("博主追踪", "B站博主")]
        # 加载已有数据用于合并
        old_articles = []
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                old_articles = old_data.get("articles", [])
        except Exception:
            old_articles = []

    all_articles = []
    for name, scraper in scrapers:
        # 时间预算：剩余时间 < 10s 跳过后续平台
        if time.time() > IMPORT_DEADLINE - 10:
            print(f"  ⏭️ {name}: 时间不足，跳过")
            FAILED_PLATFORMS.append(name)
            continue
        try:
            t0 = time.time()
            result = scraper()
            all_articles.extend(result)
            elapsed = time.time() - t0
            print(f"  ✅ {name}: {len(result)} 条 ({elapsed:.0f}s)")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            FAILED_PLATFORMS.append(name)

    # remote 模式：合并新博主数据到已有 data.json
    if mode == "remote" and old_articles:
        new_blogger_ids = {str(a["id"]) for a in all_articles}
        # 保留旧数据中非博主的文章 + 旧博主中有 analysis 的
        for a in old_articles:
            aid = str(a.get("id", ""))
            if a.get("source") == "blogger":
                if a.get("analysis") and aid not in new_blogger_ids:
                    all_articles.append(a)
            else:
                all_articles.append(a)
        print(f"  📦 合并完成: {len(all_articles)} 条 (旧非博主 + 新博主)")

    # ═══ 保留已有数据（防爬虫失败导致数据归零）═══
    old_data = None
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except:
        pass
    # full/local 模式：救援逻辑（防爬虫失败归零）
    # remote 模式已在前面合并过旧数据，跳过
    failed_sources = set()  # 始终初始化
    if mode != "remote" and old_data:
        old_articles = old_data.get("articles", [])
        # 1. 保留旧的博主数据
        #    - full 模式：只保留有 analysis 的（新数据已重新抓取，analysis 是额外附加值）
        #    - local 模式：无条件保留全部（博主爬虫被跳过，所有旧数据都需要）
        #
        # ⚠️ ASR 文案迁移：用 aweme_id 做 key（F2/PW/TikHub 的 aweme_id 一致）
        old_intro_map = {}
        for b in old_articles:
            if b.get("source") == "blogger":
                key = b.get("aweme_id") or b.get("url") or str(b.get("id"))
                if b.get("content_intro") and len(b["content_intro"]) >= 50:
                    old_intro_map[str(key)] = b["content_intro"]
        preserved = 0
        for a in all_articles:
            if a.get("source") != "blogger":
                continue
            key = str(a.get("aweme_id") or a.get("url") or str(a.get("id")))
            if key in old_intro_map and len(a.get("content_intro", "")) < 50:
                a["content_intro"] = old_intro_map[key]
                preserved += 1
        if preserved:
            print(f"  \U0001f4dd 迁移 {preserved} 条旧 ASR 文案")
        # 同时保留旧条目中 analysis 数据
        old_analysis_map = {}
        for b in old_articles:
            if b.get("source") == "blogger" and b.get("analysis"):
                key = b.get("url") or str(b.get("id"))
                if key not in old_analysis_map:
                    old_analysis_map[key] = b["analysis"]
        preserved_a = 0
        for a in all_articles:
            if a.get("source") != "blogger":
                continue
            key = a.get("url") or str(a.get("id"))
            if key in old_analysis_map and not a.get("analysis"):
                a["analysis"] = old_analysis_map[key]
                preserved_a += 1
        if preserved_a:
            print(f"  \U0001f4ca 迁移 {preserved_a} 条旧 analysis 数据")
        # 按模式决定保留哪些旧博主条目
        if mode == "local":
            old_bloggers = [a for a in old_articles if a.get("source") == "blogger"]
        else:
            old_bloggers = [a for a in old_articles if a.get("source") == "blogger" and (a.get("analysis") or a.get("content_intro"))]
        new_blogger_ids = {str(a["id"]) for a in all_articles if a.get("source") == "blogger"}
        new_blogger_urls = {a.get("url", "") for a in all_articles if a.get("source") == "blogger"}
        rescued_bloggers = 0
        for b in old_bloggers:
            # 保留新数据中没有的旧条目（按ID和URL双重去重）
            if str(b["id"]) not in new_blogger_ids and b.get("url", "") not in new_blogger_urls:
                all_articles.append(b)
                rescued_bloggers += 1
        if rescued_bloggers:
            print(f"  🛟 保留 {rescued_bloggers} 条旧博主数据")
        
        # 2. 失败的源 -> 保留旧数据
        failed_sources = set()
        for name, scraper in scrapers:
            if name != "博主追踪":
                source_label = {
                    "百度热搜": "百度热搜", "知乎": "知乎", "B站": "bilibili",
                    "今日头条": "今日头条", "澎湃新闻": "澎湃新闻", "华尔街见闻": "华尔街见闻",
                    "财联社": "财联社热门", "凤凰网": "凤凰网", "贴吧": "贴吧",
                    "微博": "微博", "抖音": "抖音", "公众号": "公众号热点"
                }.get(name, name)
                has_data = any(a.get("source", "") == source_label for a in all_articles)
                if not has_data:
                    failed_sources.add(source_label)
        
        if failed_sources:
            old_rescue = [a for a in old_articles 
                          if a.get("source") in failed_sources and a.get("source") != "blogger"]
            if old_rescue:
                print(f"  🛟 保留 {len(old_rescue)} 条旧数据 (来自: {', '.join(failed_sources)})")
                all_articles.extend(old_rescue)
        
        # 3. 始终合并旧的非博主数据（按URL去重），确保保留3天历史
        old_non_blogger = [a for a in old_articles if a.get("source") != "blogger"]
        new_non_blogger_urls = {a.get("url", "") for a in all_articles if a.get("source") != "blogger"}
        merged_old = 0
        for a in old_non_blogger:
            old_url = a.get("url", "")
            if old_url and old_url not in new_non_blogger_urls:
                all_articles.append(a)
                new_non_blogger_urls.add(old_url)
                merged_old += 1
        if merged_old:
            print(f"  📦 合并 {merged_old} 条旧新闻数据（保留3天历史）")
    
    # 去重（按id）
    seen = set()
    unique_articles = []
    for a in all_articles:
        aid = str(a.get("id", ""))
        if aid and aid not in seen:
            seen.add(aid)
            unique_articles.append(a)
    all_articles = unique_articles
    
    # ═══ 全局清洗：去掉 HTML 标签 + 过滤空标题 ═══
    for a in all_articles:
        # 清洗标题和摘要中的 HTML 标签
        a["title"] = re.sub(r"<[^>]+>", "", a.get("title", "") or "").strip()
        a["summary"] = re.sub(r"<[^>]+>", "", a.get("summary", "") or "").strip()
    # 过滤无标题的文章
    before = len(all_articles)
    all_articles = [a for a in all_articles if (a.get("title") or "").strip()]
    if len(all_articles) < before:
        print(f"  U0001f9f9 过滤 {before - len(all_articles)} 条空标题")

    
    # 每个博主：先按标题去重（同一视频可能因 ID 不同产生两条），再保留最新 3 条
    blogger_by_name = {}
    for a in all_articles:
        if a.get("source") == "blogger":
            name = a.get("blogger_name", "未知")
            if name not in blogger_by_name:
                blogger_by_name[name] = []
            blogger_by_name[name].append(a)
    
    for name, items in blogger_by_name.items():
        # 按标题去重：如果 title_A 包含 title_B 或 title_B 包含 title_A，保留 ID 较短的那个（新数据）
        deduped = []
        removed_ids = set()
        for item in items:
            title = item.get("title", "")
            dup = False
            for existing in deduped:
                ext = existing.get("title", "")
                if title and ext:
                    # 去掉 [博主名] 前缀后比较
                    clean_a = re.sub(r'^\[.*?\]\s*', '', title).strip()
                    clean_b = re.sub(r'^\[.*?\]\s*', '', ext).strip()
                    if clean_a and clean_b and len(clean_a) >= 10 and len(clean_b) >= 10:
                        # 只有短标题是长标题的 80% 以上才判为重复
                        shorter = clean_a if len(clean_a) < len(clean_b) else clean_b
                        longer = clean_b if len(clean_a) < len(clean_b) else clean_a
                        if shorter in longer and len(shorter) >= len(longer) * 0.8:
                            dup = True
                            break
            if not dup:
                deduped.append(item)
            else:
                removed_ids.add(str(item.get("id", "")))
        # 从 all_articles 中移除被标题去重掉的条目
        if removed_ids:
            all_articles = [a for a in all_articles if str(a.get("id","")) not in removed_ids]
        deduped.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)
        blogger_by_name[name] = deduped
    
    # 清理旧版 [博主名] 标题前缀
    for a in all_articles:
        if a.get("source") == "blogger":
            name = a.get("blogger_name", "")
            if name:
                a["title"] = re.sub(rf'^\[{re.escape(name)}\]\s*', '', a.get("title", ""))
    
    # 保留最新 3 条，移除超出部分
    
    for name, items in blogger_by_name.items():
        items.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)
        kept = items[:3]
        removed = items[3:]
        if removed:
            removed_ids = {str(r["id"]) for r in removed}
            all_articles = [a for a in all_articles if str(a["id"]) not in removed_ids]
            print(f"  🧹 {name}: 保留 {len(kept)} 条，移除 {len(removed)} 条旧数据")

    # 生成灵感（函数内部自动按抖音爆火潜力从全量筛50条）
    # 生成灵感（函数内部自动按抖音爆火潜力从全量筛50条）
    inspirations = generate_inspirations(all_articles)

    # ═══ 消毒：移除所有字符串中的换行符、回车、制表符（防止 HTML 内联 JSON 出错）═══
    for a in all_articles:
        for k in ('title', 'summary', 'content_intro'):
            if k in a and isinstance(a[k], str):
                a[k] = a[k].replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    
    # 为缺少/过短 content_intro 的博主视频补充基础简介（不覆盖 F2/ASR 已提取的实质内容）
    for a in all_articles:
        if a.get("source") == "blogger":
            ci = a.get("content_intro", "")
            # 空或过短（<80字且无真实F2/ASR内容标识）→ 重新生成
            if not ci or (len(ci) < 80 and not any(kw in ci for kw in ['进行了','描述了','讲述了','还原','经过','视频中','完整','👍','赞','评论','分享'])):
                a["content_intro"] = _generate_video_intro(a, all_articles)

    # ═══ 文案清洗：繁转简 + Whisper误识别修复 ═══
    _clean_fixes = [
        ('无警广员支队银门哨兵','武警执勤'),('虎帐办演者','cosplay表演者'),
        ('虎帐优人','coser'),('枪都已经向堂了','枪都已经上膛了'),
        ('托落','脱落'),('昏觉','昏厥'),('灯上热搜','登上热搜'),
        ('推桑','推搡'),('设施六人','涉案六人'),('户在身后','护在身后'),
        ('富哨','副哨'),('烫手山狱','烫手山芋'),('切开的稀釉','切开的西瓜'),
        ('六官王','六冠王'),('对势','对峙'),('慢展','漫展'),('苏行定徽','苏醒后'),
        ('炼铜皮','恋童癖'),('黑闪酒机','黑闪连击'),('拒留','拘留'),
        ('罩人男子','肇事男子'),('首部受伤','头部受伤'),('毒瘤女孩','盲人女孩'),
        ('将警快核实','将尽快核实'),('全之龙','权志龙'),('其不来的','起不来的'),
        ('图件进攻','推荐进攻'),('彼此根','培根'),('鲜耳朵','馅儿多'),
        ('三娘我请我来哦',''),('你爆一个四十','你爆一个试试'),
        ('浓的要小','弄的要死'),('恰人中等急救措施','掐人中急救'),
        ('不是陷入','不适陷入'),
    ]
    _zhe = [('想著','想着'),('握著','握着'),('看著','看着'),('对著','对着'),
            ('拿著','拿着'),('跟著','跟着'),('推著','推着'),('抱著','抱着'),
            ('走著','走着'),('笑著','笑着'),('吃著','吃着'),('站著','站着')]
    try:
        from opencc import OpenCC
        _cc = OpenCC('t2s')
        for a in all_articles:
            ci = a.get('content_intro','')
            if not ci: continue
            try: ci = _cc.convert(ci)
            except: pass
            for w,r in _zhe: ci=ci.replace(w,r)
            for w,r in _clean_fixes: ci=ci.replace(w,r)
            a['content_intro'] = ci.strip()
    except ImportError:
        pass
    # 为缺少 analysis 的博主视频自动生成
    for a in all_articles:
        if a.get("source") == "blogger" and not a.get("analysis"):
            a["analysis"] = generate_blogger_analysis(a)

    # 构建 data.json
    # ═══ 数据过滤 ═══
    from datetime import timedelta
    cutoff = datetime.now().date() - timedelta(days=2)           # 新闻保留3天（今天+2天前=3天窗口）
    rescue_cutoff = datetime.now().date() - timedelta(days=6)   # 失败平台保留7天
    blog_cutoff = datetime.now().date() - timedelta(days=3)      # 博主3天
    fresh = []
    bloggers_kept = {}
    blog_removed = 0
    news_removed = 0
    for a in all_articles:
        if a.get("source") == "blogger":
            name = a.get("blogger_name", "")
            lst = bloggers_kept.setdefault(name, [])
            lst.append(a)
        else:
            src = a.get("source", "")
            # 失败平台：7天保护期，成功平台：3天
            limit = rescue_cutoff if src in failed_sources else cutoff
            try:
                date_str = (a.get("date") or a.get("published_at") or "")[:10]
                if not date_str:
                    news_removed += 1
                    continue
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                if d < limit:
                    news_removed += 1
                    continue
            except ValueError:
                news_removed += 1
                continue
            fresh.append(a)
    # 博主：保留3天内最新3条
    for name, lst in bloggers_kept.items():
        # 只保留3天内的
        recent = []
        old = 0
        for a in lst:
            try:
                date_str = (a.get("date") or a.get("published_at") or "")[:10]
                if not date_str:
                    old += 1
                    continue
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                if d < blog_cutoff:
                    old += 1
                    continue
                recent.append(a)
            except ValueError:
                old += 1
                continue
        recent.sort(key=lambda x: x.get("date","") or x.get("published_at","") or "", reverse=True)
        fresh.extend(recent[:3])
        blog_removed += old + max(0, len(recent) - 3)
    if blog_removed:
        print(f"  🗑 博主过期: {blog_removed} 条")
    if news_removed:
        print(f"  🗑 新闻过期: {news_removed} 条")
    all_articles = fresh

    # ═══ 🔒 最终保护层：确保每条博主视频都有可读文案，绝不丢失 ═══
    _lost_ci = 0
    for a in all_articles:
        if a.get("source") != "blogger":
            continue
        ci = a.get("content_intro", "") or ""
        title = a.get("title", "") or ""
        summary = a.get("summary", "") or ""
        likes = a.get("likes", 0) or 0
        comments = a.get("comments", 0) or 0
        
        # 已有实质内容（>50字且不是"📹"开头）→ 保留
        if len(ci) > 50 and not ci.startswith("📹"):
            continue
        
        # 重建文案：优先用 summary，降级用 title
        base = summary if len(summary) > 20 else title
        if not base or len(base) < 3:
            continue
        
        parts = [base]
        if likes > 0:
            parts.append(f"👍 {likes//10000}万赞" if likes >= 10000 else f"👍 {likes}赞")
        if comments > 0:
            parts.append(f"💬 {comments}评论")
        
        a["content_intro"] = "\n".join(parts)[:300]
        _lost_ci += 1
    
    if _lost_ci:
        print(f"  💾 补全 {_lost_ci} 条博主文案")

    output = {
        "site": {
            "name": SITE_NAME,
            "description": SITE_DESC,
        },
        "articles": all_articles,
        "inspirations": inspirations,
        "updated_at": datetime.now().isoformat(),
        "failed_platforms": FAILED_PLATFORMS if FAILED_PLATFORMS else None,
    }

    tmp_file = OUTPUT_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, OUTPUT_FILE)

    print(f"\n✅ 生成完成: {len(all_articles)} 条热点 + {len(inspirations)} 条灵感")
    print(f"   输出文件: {OUTPUT_FILE}")

    # ═══ 自动更新 index.html + data.js（外部引用，支持 CDN 缓存） ═══
    try:
        import subprocess as _sp
        gen_js = os.path.join(BASE_DIR, "gen_js_data.py")
        r = _sp.run([sys.executable, gen_js], cwd=BASE_DIR, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            print(f"   {r.stdout.strip()}")
        else:
            print(f"   ⚠️ gen_js_data 失败: {r.stderr[:100]}")
    except Exception as e:
        print(f"   ⚠️ gen_js_data 异常: {e}")

    return len(all_articles) > 0


def _generate_video_intro(v, all_articles):
    """基于视频信息生成内容简介：有描述用描述，没有则用标题+标签+来源组合"""
    desc = (v.get("summary") or v.get("title") or "").strip()
    title = (v.get("title") or "").strip()
    tags = v.get("tags", [])
    platform = v.get("platform", "") or "抖音"
    blogger = v.get("blogger_name", "")
    
    # 有长描述就用描述
    if len(desc) > 50:
        return desc[:300]
    
    # 没有长描述，从标题+标签+上下文构建
    parts = [f"📹 {blogger}最新发布"]
    if title:
        parts.append(f"标题：{title}")
    
    # 从 tags 中提取有效标签
    useful_tags = [t for t in tags if t not in ("博主", "爆款", "拆解", "B站", "热点", "资讯", "社会") and len(t) > 1]
    if useful_tags:
        parts.append("标签：" + " ".join("#" + t for t in useful_tags[:6]))
    
    # 补充点赞数
    likes = v.get("likes", 0)
    if likes > 1000:
        parts.append(f"👍 {likes//10000}万赞" if likes >= 10000 else f"👍 {likes}赞")
    
    if blogger and platform and platform not in str(parts[-1]):
        parts.append(f"来源：{blogger}（{platform}）")
    
    result = "\n".join(parts) if parts else desc
    return result[:300]


if __name__ == "__main__":
    import sys
    mode = "full"
    if "--local" in sys.argv:
        mode = "local"
    elif "--remote" in sys.argv:
        mode = "remote"
    success = main(mode=mode)
    exit(0 if success else 1)
