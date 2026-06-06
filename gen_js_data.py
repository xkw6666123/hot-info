#!/usr/bin/env python3
"""数据写入：内联嵌入 + 同时生成 data.js 兜底"""
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

def sanitize_for_js(obj):
    if isinstance(obj, str):
        return re.sub(r'</script>', r'<\/script>', obj, flags=re.IGNORECASE)
    elif isinstance(obj, dict):
        return {k: sanitize_for_js(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_js(item) for item in obj]
    return obj

def optimize_articles(articles):
    optimized = []
    for a in articles:
        if a.get("source") == "blogger":
            optimized.append(a)
        else:
            item = {
                "id": a.get("id"), "title": a.get("title"),
                "source": a.get("source"), "date": a.get("date"),
                "time": a.get("time"), "url": a.get("url"),
                "likes": a.get("likes", 0),
            }
            s = str(a.get("summary", "") or "")
            if len(s) > 80: s = s[:80] + "..."
            item["summary"] = s
            tags = a.get("tags", [])
            if isinstance(tags, list) and tags:
                item["tags"] = tags[:3]
            optimized.append(item)
    return optimized

def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    
    data["articles"] = optimize_articles(data["articles"])
    data = sanitize_for_js(data)
    
    js_body = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    version = str(int(time.time()))
    
    # 同时写 data.js（给 loadData 做兜底）
    atomic_write("data.js", f"window.__HOT_DATA__={js_body};\n", newline="\n")
    
    # 内联嵌入到 index.html
    inline_tag = f'<script data-embed>\nwindow.__HOT_DATA__={js_body};\n</script>'
    
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    # 替换外部引用 → 内联
    html = re.sub(r'<script src="data\.js\?v=\d+"[^>]*></script>', lambda m: inline_tag, html)
    # 替换旧内联
    html = re.sub(r'<script data-embed>[\s\S]*?</script>', lambda m: inline_tag, html)
    
    atomic_write("index.html", html, newline="\n")
    
    print(f"[OK] index.html: {len(html)//1024}KB (内联数据 {len(js_body)//1024}KB)")

if __name__ == "__main__":
    main()
