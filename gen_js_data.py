#!/usr/bin/env python3
"""数据写入：生成外部 data.js，index.html 通过 <script src> 异步加载"""
import json, os, re, time
from datetime import datetime

def atomic_write(path, content, mode="w", encoding="utf-8", newline=None):
    # Windows 沙盒可能禁止在目标目录创建 .tmp，先写到当前工作目录再移动
    base = os.path.basename(path)
    tmp = os.path.join(os.getcwd(), base + ".tmp")
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
    try:
        with open("data.json", "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        
        data["articles"] = optimize_articles(data["articles"])
        data = sanitize_for_js(data)
        
        js_body = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        version = str(int(time.time()))
        
        # 只写外部 data.js，不再内联到 index.html
        atomic_write("data.js", f"window.__HOT_DATA__={js_body};\n", newline="\n")
        
        # 更新 index.html 中的 script src 版本号（兼容有/无版本号、单双引号）
        html_path = "index.html"
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            # 替换已有 data.js 引用（兼容 defer/async/无版本号/单双引号）
            new_html = re.sub(r'<script src=["\']data\.js(?:\?v=[^"\']*)?["\'][^>]*>', f'<script src="data.js?v={version}" defer>', html)
            # 如果没有 data.js 引用但存在其他 script 标签前，插入引用
            if 'data.js' not in new_html:
                new_html = new_html.replace('<script>', f'<script src="data.js?v={version}" defer></script>\n<script>', 1)
            if new_html != html:
                atomic_write(html_path, new_html, newline="\n")
        
        print(f"[OK] data.js: {len(js_body)//1024}KB (v={version})")
    except Exception as e:
        print(f"[ERROR] gen_js_data.py failed: {e}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
