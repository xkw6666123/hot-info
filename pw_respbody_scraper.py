#!/usr/bin/env python3
"""免费抖音博主视频抓取 — playwright-cli response-body 方案
核心: 打开页面 → 等待API调用 → response-body获取数据 → 关闭
"""
import json, os, sys, time, re, subprocess, hashlib
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
PCLI = "playwright-cli"

TODAY = datetime.now().strftime("%Y-%m-%d")
NOW = datetime.now().strftime("%H:%M")

BLOGGERS = {
    "网吧信息差": "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv",
    "阿七大型纪录片": "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf",
    "陈先生": "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF",
    "人类观察菌": "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN",
}


def make_id(prefix, seed):
    return int(hashlib.md5(f"{prefix}_{seed}".encode()).hexdigest()[:8], 16) % 10 ** 9


def scrape_one(name, sec_uid):
    """用单次bash会话抓取单个博主"""
    # 构建一个连续的bash命令序列
    script = f"""
unset NODE_OPTIONS
{PCLI} kill-all >/dev/null 2>&1
sleep 2
{PCLI} open "https://www.douyin.com/user/{sec_uid}" >/dev/null 2>&1
sleep 18

# 找aweme/post请求的索引
IDX=$({PCLI} requests 2>/dev/null | grep 'aweme/v1/web/aweme/post.*count=18' | head -1 | grep -oP '^\\s*\\K\\d+')

if [ -n "$IDX" ]; then
    # 获取响应体
    {PCLI} response-body $IDX 2>/dev/null
else
    echo 'NO_IDX'
fi

{PCLI} close >/dev/null 2>&1
"""
    try:
        r = subprocess.run(
            ["bash", "-c", script],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} close"], capture_output=True, timeout=5)
        return []

    output = r.stdout.strip()
    if not output or output == "NO_IDX":
        return []

    # 尝试解析JSON
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        # 响应可能是gzip过的或者是多行格式
        return []

    aweme_list = data.get("aweme_list", [])
    return [
        {
            "aweme_id": str(v.get("aweme_id", "")),
            "desc": (v.get("desc", "") or "")[:200],
            "likes": (v.get("statistics", {}) or {}).get("digg_count", 0),
            "comments": (v.get("statistics", {}) or {}).get("comment_count", 0),
            "create_time": v.get("create_time", 0),
        }
        for v in aweme_list
    ]


def scrape_bloggers_respbody():
    """主函数"""
    articles = []

    for name, sec_uid in BLOGGERS.items():
        print(f"📹 {name}...")
        try:
            videos = scrape_one(name, sec_uid)
        except Exception as e:
            print(f"  ❌ {e}")
            continue

        print(f"  {len(videos)}条")
        for v in videos[:5]:
            aweme_id = v.get("aweme_id", "")
            desc = v.get("desc", "")
            create_time = v.get("create_time", 0)
            date = TODAY
            t = NOW
            if create_time:
                try:
                    dt = datetime.fromtimestamp(int(create_time))
                    date = dt.strftime("%Y-%m-%d")
                    t = dt.strftime("%H:%M")
                except:
                    pass

            articles.append({
                "id": make_id("resp", f"{name}_{aweme_id}") % 10**9,
                "title": desc[:80] if desc else f"{name} 最新视频",
                "summary": desc,
                "source": "blogger",
                "blogger_name": name,
                "date": date, "time": t,
                "tags": ["博主", "爆款", "拆解"],
                "url": f"https://www.douyin.com/video/{aweme_id}",
                "likes": v.get("likes", 0),
                "comments": v.get("comments", 0),
                "aweme_id": aweme_id,
            })
            print(f"    {v.get('likes',0)}赞 {desc[:50]}")

    return articles


if __name__ == "__main__":
    articles = scrape_bloggers_respbody()
    print(f"\n总计: {len(articles)}条")
