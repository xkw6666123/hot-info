#!/usr/bin/env python3
"""
数据写入 data.js，避免 fetch + 编码问题
同时更新 index.html 中的缓存版本号
"""
import json
import os
import re
from datetime import datetime

def main():
    # 读取 data.json（去掉可能的 BOM）
    with open("data.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    
    # 输出到 data.js 作为全局变量
    js = f"window.__HOT_DATA__ = {json.dumps(data, ensure_ascii=False, indent=0)};\n"
    
    # 写入时不加 BOM（utf-8 不加 BOM，与 utf-8-sig 不同）
    with open("data.js", "w", encoding="utf-8", newline="\n") as f:
        f.write(js)
    
    # 二次确认：如果写入了 BOM 则去掉
    with open("data.js", "rb") as f:
        raw = f.read()
    if raw[:3] == b'\xef\xbb\xbf':
        with open("data.js", "wb") as f:
            f.write(raw[3:])
        print(f"[BOM] removed")

    # 更新 index.html 的缓存版本号（破坏浏览器/CDN 缓存）
    ver = datetime.now().strftime("%Y%m%d%H%M")
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    html = re.sub(r'data\.js\?v=\d+', f'data.js?v={ver}', html)
    with open("index.html", "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    print(f"[OK] data.js done ({len(js)} bytes)")

if __name__ == "__main__":
    main()
