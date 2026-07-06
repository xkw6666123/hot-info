#!/usr/bin/env python3
"""生成外部 data.js + inspiration.js 分离加载，减小首屏体积"""
import json, os, re, time

def atomic_write(path, content, newline=None):
    base = os.path.basename(path)
    tmp = os.path.join(os.getcwd(), base + ".tmp")
    kw = {"encoding": "utf-8"}
    if newline: kw["newline"] = newline
    with open(tmp, "w", **kw) as f:
        f.write(content)
    os.replace(tmp, path)

def sanitize(obj):
    if isinstance(obj, str):
        return re.sub(r'</script>', r'<\/script>', obj, flags=re.IGNORECASE)
    elif isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize(x) for x in obj]
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
            if len(s) > 50: s = s[:50] + "..."
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
        
        # ═══ 分离灵感到独立文件 ═══
        inspirations = data.pop("inspirations", []) if "inspirations" in data else []
        insp_count = len(inspirations)
        data["inspiration_count"] = insp_count  # 页面显示数量，但不在首屏加载
        
        data["articles"] = optimize_articles(data["articles"])
        data = sanitize(data)
        
        version = str(int(time.time()))
        
        # 1. data.js — 不含灵感
        js_body = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        atomic_write("data.js", f"window.__HOT_DATA__={js_body};\n", newline="\n")
        
        # 2. inspiration.js — 独立灵感文件
        insp_data = sanitize(inspirations)
        insp_js = json.dumps(insp_data, ensure_ascii=False, separators=(',', ':'))
        atomic_write("inspiration.js", f"window.__INSP_DATA__={insp_js};\n", newline="\n")
        
        # 3. 更新 index.html 版本号
        html_path = "index.html"
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            new_html = re.sub(
                r'<script src=["\']data\.js(?:\?v=[^"\']*)?["\'][^>]*>',
                f'<script src="data.js?v={version}" defer></script>',
                html
            )
            if 'data.js' not in new_html:
                new_html = new_html.replace('<script>', f'<script src="data.js?v={version}" defer></script>\n<script>', 1)
            if new_html != html:
                atomic_write(html_path, new_html, newline="\n")
        
        print(f"[OK] data.js: {len(js_body)//1024}KB | inspiration.js: {len(insp_js)//1024}KB | v={version}")
    except Exception as e:
        print(f"[ERROR] gen_js_data.py failed: {e}")
        import sys; sys.exit(1)

if __name__ == "__main__":
    main()
