#!/usr/bin/env python3
"""
数据写入 data.js，避免 fetch + 编码问题
"""
import json
from datetime import datetime

def main():
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 输出到 data.js 作为全局变量
    js = f"window.__HOT_DATA__ = {json.dumps(data, ensure_ascii=False, indent=0)};\n"
    
    with open("data.js", "w", encoding="utf-8") as f:
        f.write(js)
    
    print(f"✅ data.js 生成完成 ({len(js)} bytes)")

if __name__ == "__main__":
    main()
