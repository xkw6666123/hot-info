#!/usr/bin/env python3
"""数据写入 data.js，原子化防损坏 + 缓存版本号更新"""
import json, os, re
from datetime import datetime

def atomic_write(path, content, mode="w", encoding="utf-8", newline=None):
    """原子写入：先写临时文件，再 replace 到目标"""
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
    
    js = f"window.__HOT_DATA__ = {json.dumps(data, ensure_ascii=False, indent=0)};\n"
    atomic_write("data.js", js, newline="\n")
    
    ver = datetime.now().strftime("%Y%m%d%H%M")
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    html = re.sub(r'data\.js\?v=\d+', f'data.js?v={ver}', html)
    atomic_write("index.html", html, newline="\n")
    
    print(f"[OK] data.js done ({len(js)} bytes)")

if __name__ == "__main__":
    main()
