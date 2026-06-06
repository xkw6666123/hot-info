#!/usr/bin/env python3
"""数据写入：生成独立 data.js + 外部引用，让浏览器和 CDN 各自缓存"""
import json, os, re, time
from datetime import datetime

def atomic_write(path, content, mode="w", encoding="utf-8", newline=None):
    tmp = path + ".tmp"
    kwargs = {"encoding": encoding}
    if newline: kwargs["newline"] = newline
    if "b" in mode:
        with open(tmp, mode) as f: f.write(content)
    else:
        with open(tmp, mode, **kwargs) as f: f.write(content)
    os.replace(tmp, path)

def optimize_articles(articles):
    """精简非博主文章：去掉 comments，缩短摘要，减少体积"""
    optimized = []
    for a in articles:
        if a.get("source") == "blogger":
            optimized.append(a)
        else:
            item = {
                "id": a.get("id"),
                "title": a.get("title"),
                "source": a.get("source"),
                "date": a.get("date"),
                "time": a.get("time"),
                "url": a.get("url"),
                "likes": a.get("likes", 0),
            }
            s = str(a.get("summary", "") or "")
            if len(s) > 80:
                s = s[:80] + "..."
            item["summary"] = s
            tags = a.get("tags", [])
            if isinstance(tags, list) and tags:
                item["tags"] = tags[:3]
            optimized.append(item)
    return optimized

def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    
    # 精简非博主文章
    data["articles"] = optimize_articles(data["articles"])
    
    # 生成紧凑 JSON
    js_body = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    version = str(int(time.time()))
    
    # 写入独立 data.js（带版本号防缓存）
    data_js = f"window.__HOT_DATA__={js_body};\n"
    atomic_write("data.js", data_js, newline="\n")
    print(f"[OK] data.js: {len(data_js)//1024}KB (v={version})")
    
    # 更新 index.html：用外部引用替代内联
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    script_tag = f'<script src="data.js?v={version}"></script>'
    
    # 替换内联 data-embed
    old_inline = r'<script data-embed>[\s\S]*?</script>'
    html = re.sub(old_inline, lambda m: script_tag, html)
    
    # 替换旧版外部引用
    old_ext = r'<script src="data\.js\?v=\d+"[^>]*></script>'
    html = re.sub(old_ext, lambda m: script_tag, html)
    
    atomic_write("index.html", html, newline="\n")
    
    html_size = len(html.replace(script_tag, ""))  # 不含数据的大小
    print(f"[OK] index.html: {html_size//1024}KB (模板) + data.js 外部引用")

if __name__ == "__main__":
    main()
