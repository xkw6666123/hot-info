#!/usr/bin/env python3
"""数据写入：把 data.json 直接嵌入 index.html 内联脚本，消除外部文件依赖"""
import json, os, re
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

def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    
    # 生成内联脚本内容
    inline_js = f"\nwindow.__HOT_DATA__ = {json.dumps(data, ensure_ascii=False, indent=0)};\n"
    
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    # 替换旧的 data.js 引用 -> 内联脚本
    # 匹配: <script src="data.js?v=...">...onerror...</script>
    old_pattern = r'<script src="data\.js\?v=\d+"[^>]*>[\s\S]*?</script>'
    new_tag = f'<script data-embed>{inline_js}</script>'
    html = re.sub(old_pattern, new_tag, html)
    
    atomic_write("index.html", html, newline="\n")
    
    print(f"[OK] 数据已嵌入 index.html ({len(inline_js)} bytes) 取代外部 data.js")

if __name__ == "__main__":
    main()
