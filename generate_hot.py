#!/usr/bin/env python3
"""
自动化热点数据采集脚本 (GitHub Actions 用)
来源: 百度/知乎/哔哩哔哩/今日头条/澎湃/华尔街见闻/财联社/凤凰/贴吧/微博/抖音/公众号
"""
import json
import os
import re
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
TIMEOUT = 15
RETRIES = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# ── TikHub 博主追踪 ──
TIKHUB_API_KEY = os.environ.get("TIKHUB_API_KEY", "srAlG/ROjGy6h0XKAoib+DTMbQKKX6Ns/SbJvkumTaW8jVOVPVyHSROeOw==")
TIKHUB_BASE = "https://api.tikhub.io"
TIKHUB_TIMEOUT = 30

# 追踪的博主列表: 填博主抖音名称即可；如遇重名可用 {"name": "陈先生", "user_id": "MS4wLjAB..."} 硬编码
TRACKED_BLOGGERS = [
    "网吧信息差",
    "阿七大型纪录片",
    {"name": "陈先生", "user_id": "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF"},  # chenxiansheng274 8.9万粉丝
    "信息黑板报",
    "人类观察菌",
]

# B站博主追踪: name + mid (UID)
BILI_BLOGGERS = [
    {"name": "沙漠一之雕", "mid": "283204224"},
]

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
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": f"https://space.bilibili.com/{mid}",
                })
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(req, timeout=TIMEOUT) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                    code = data.get("code")
                    if code == 0:
                        break
                    elif code == -799:
                        time.sleep(8 * (attempt + 1))
                    else:
                        time.sleep(2)
            except Exception as e:
                if attempt < 2:
                    time.sleep(8 * (attempt + 1))
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
    """华尔街见闻（实时快讯API，无重复）"""
    print("📡 华尔街见闻...")
    data = fetch_json("https://api-one.wallstcn.com/apiv1/content/lives?limit=10&channel=global-channel",
                      referer="https://wallstreetcn.com/")
    if not data:
        return []
    articles = []
    seen_ids = set()
    for item in data.get("data", {}).get("items", [])[:10]:
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
            "likes": 15000, "comments": 150,
        })
    return articles

def scrape_cls():
    """财联社"""
    print("📡 财联社...")
    data = fetch_json("https://www.cls.cn/nodeapi/updateTelegraphList",
                      referer="https://www.cls.cn/")
    if not data or not data.get("data"):
        return []
    articles = []
    items = data.get("data", {}).get("roll_data", [])
    for item in items[:10]:
        articles.append({
            "id": make_id("cls", str(item.get('id',''))) % 10**9,
            "title": item.get("title", ""),
            "summary": item.get("brief", "")[:100],
            "source": "财联社热门",
            "date": today, "time": now_time,
            "tags": ["财经", "金融", "投资"],
            "url": f"https://www.cls.cn/detail/{item.get('id','')}",
            "likes": 20000, "comments": 200,
        })
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
        "Cookie": "SUB=_2AkMRK_L_f8NxqwJRmP4WyG3haYh0wgnEieKkZxRJRMxHRl-yT9kqmgntRB6OJuL3Q2LFz2Jko5w4o7B3eMUZJQoL_5PW;"
    }
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
    for item in data.get("data", {}).get("word_list", [])[:10]:
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

def main(mode="full"):
    """
    mode: "full"=全部爬虫, "local"=跳过TikHub/B站博主, "remote"=只跑TikHub/B站+合并已有数据
    """
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
        ("博主追踪", scrape_bloggers),
    ]
    
    if mode == "local":
        # local 模式也跑博主追踪：TikHub API 国内直连可用，B站 API 国内直连
        # 只跳过需要 cookie/签名的抖音直抓
        scrapers = [(n, s) for n, s in scrapers if n not in ("抖音",)]
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
        try:
            result = scraper()
            all_articles.extend(result)
            print(f"  ✅ {name}: {len(result)} 条")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

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
        if mode == "local":
            old_bloggers = [a for a in old_articles if a.get("source") == "blogger"]
            # 把旧 ASR 文案迁移到新条目（TikHub 数据无高质量文案）
            old_intro_map = {}
            for b in old_bloggers:
                key = b.get("url") or str(b.get("id"))
                if b.get("content_intro") and len(b["content_intro"]) >= 50:
                    old_intro_map[key] = b["content_intro"]
            preserved = 0
            for a in all_articles:
                if a.get("source") != "blogger":
                    continue
                key = a.get("url") or str(a.get("id"))
                if key in old_intro_map and len(a.get("content_intro", "")) < 50:
                    a["content_intro"] = old_intro_map[key]
                    preserved += 1
            if preserved:
                print(f"  \U0001f4dd 保留 {preserved} 条旧 ASR 文案")
        else:
            old_bloggers = [a for a in old_articles if a.get("source") == "blogger" and a.get("analysis")]
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
        
        # 3. 如果新数据太少，额外保留所有旧的非博主数据
        new_count = len([a for a in all_articles if a.get("source") != "blogger"])
        old_count = len([a for a in old_articles if a.get("source") != "blogger"])
        if new_count < 30 and old_count > 50:
            extra = [a for a in old_articles if a.get("source") != "blogger"]
            existing_ids = {str(a["id"]) for a in all_articles}
            added = 0
            for a in extra:
                if str(a["id"]) not in existing_ids:
                    all_articles.append(a)
                    existing_ids.add(str(a["id"]))
                    added += 1
            if added:
                print(f"  🛟 新数据太少({new_count}条)，额外保留 {added} 条旧数据")
    
    # 去重（按id）
    seen = set()
    unique_articles = []
    for a in all_articles:
        aid = str(a.get("id", ""))
        if aid and aid not in seen:
            seen.add(aid)
            unique_articles.append(a)
    all_articles = unique_articles
    
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

    # 生成灵感（优先博主内容）
    blogger_items = [a for a in all_articles if a.get("source") == "blogger"]
    other_items = [a for a in all_articles if a.get("source") != "blogger"]
    insp_sources = blogger_items[:3] + other_items[:12]
    inspirations = generate_inspirations(insp_sources[:15])

    # 为缺少 content_intro 的博主视频补充基础简介（不覆盖 ASR 已提取的内容）
    for a in all_articles:
        if a.get("source") == "blogger" and not a.get("content_intro"):
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
    cutoff = datetime.now().date() - timedelta(days=7)           # 新闻保留7天
    rescue_cutoff = datetime.now().date() - timedelta(days=14)   # 失败平台保留14天
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
                d = datetime.strptime((a.get("date") or a.get("published_at") or "")[:10], "%Y-%m-%d").date()
                if d < limit:
                    news_removed += 1
                    continue
            except:
                pass
            fresh.append(a)
    # 博主：保留3天内最新3条
    for name, lst in bloggers_kept.items():
        # 只保留3天内的
        recent = []
        old = 0
        for a in lst:
            try:
                d = datetime.strptime((a.get("date") or a.get("published_at") or "")[:10], "%Y-%m-%d").date()
                if d < blog_cutoff:
                    old += 1
                    continue
                recent.append(a)
            except:
                recent.append(a)
        recent.sort(key=lambda x: x.get("date","") or x.get("published_at","") or "", reverse=True)
        fresh.extend(recent[:3])
        blog_removed += old + max(0, len(recent) - 3)
    if blog_removed:
        print(f"  🗑 博主过期: {blog_removed} 条")
    if news_removed:
        print(f"  🗑 新闻过期: {news_removed} 条")
    all_articles = fresh

    output = {
        "site": {
            "name": SITE_NAME,
            "description": SITE_DESC,
        },
        "articles": all_articles,
        "inspirations": inspirations,
        "updated_at": datetime.now().isoformat(),
    }

    tmp_file = OUTPUT_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, OUTPUT_FILE)

    print(f"\n✅ 生成完成: {len(all_articles)} 条热点 + {len(inspirations)} 条灵感")
    print(f"   输出文件: {OUTPUT_FILE}")

    return len(all_articles) > 0


def _generate_video_intro(v, all_articles):
    """基于视频 desc 生成内容简介（不在没有 ASR 时伪造内容）"""
    desc = (v.get("summary") or v.get("title") or "").strip()
    
    # 有长描述就用描述
    if len(desc) > 20:
        return desc[:300]
    
    # 描述太短时，标记为"有待提取"
    return ""


if __name__ == "__main__":
    import sys
    mode = "full"
    if "--local" in sys.argv:
        mode = "local"
    elif "--remote" in sys.argv:
        mode = "remote"
    success = main(mode=mode)
    exit(0 if success else 1)
