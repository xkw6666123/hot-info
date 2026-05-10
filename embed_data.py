#!/usr/bin/env python3
"""
将 data.json 嵌入 index.html 的 EMBEDDED_B64 变量
确保页面首次加载不依赖外部 fetch
"""
import base64
import re
import json

def main():
    # 读取 data.json
    with open("data.json", "r", encoding="utf-8") as f:
        data_str = f.read()
    
    # 验证 JSON
    json.loads(data_str)
    
    # Base64 编码
    new_b64 = base64.b64encode(data_str.encode("utf-8")).decode("ascii")
    
    # 读取 index.html
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    # 替换 EMBEDDED_B64
    pattern = r'const EMBEDDED_B64 = "([^"]*)";'
    match = re.search(pattern, html)
    if not match:
        print("⚠️ 未找到 EMBEDDED_B64, 跳过")
        return
    
    old_b64 = match.group(1)
    new_html = html.replace(old_b64, new_b64)
    
    # 写回
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)
    
    print(f"✅ EMBEDDED_B64 已更新 ({len(new_b64)} chars)")

if __name__ == "__main__":
    main()
