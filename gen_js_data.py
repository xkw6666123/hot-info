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

def sanitize_for_js(obj):
    """递归处理对象，确保可以安全嵌入 <script> 标签内的 JS 赋值语句。

    核心问题：
    - JSON 字符串里的 </script>（任意大小写）会让 HTML 解析器提前关闭 script 标签
    - 解决方式：把 '/' 转义为 '\/' (JS 字符串里 \/ 等于 /)
    - json.dumps 已经处理了引号/换行等，只需额外处理 </script>
    """
    if isinstance(obj, str):
        # 大小写不敏感替换所有 </script> 变体为 <\/script>
        return re.sub(r'</script>', r'<\/script>', obj, flags=re.IGNORECASE)
    elif isinstance(obj, dict):
        return {k: sanitize_for_js(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_js(item) for item in obj]
    return obj

def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    
    # 预处理：转义 </script>，防止嵌入 JS 时打断 HTML 解析
    data = sanitize_for_js(data)
    
    # 生成内联脚本（紧凑JSON，单行，无换行问题）
    js_body = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    inline_js = f"\nwindow.__HOT_DATA__={js_body};\n"
    
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    # 替换旧的 data.js 引用 -> 内联脚本
    old_pattern = r'<script src="data\.js\?v=\d+"[^>]*>[\s\S]*?</script>'
    new_tag = f'<script data-embed>\nwindow.__HOT_DATA__={js_body};\n</script>'
    html_before = html
    html = re.sub(old_pattern, lambda m: new_tag, html)
    
    if html == html_before:
        # 旧模式没匹配到，替换已有的 data-embed 标签
        old2 = r'<script data-embed>[\s\S]*?</script>'
        html = re.sub(old2, lambda m: new_tag, html)
    
    atomic_write("index.html", html, newline="\n")
    
    print(f"[OK] 数据已嵌入 index.html ({len(inline_js)} bytes) 取代外部 data.js")

if __name__ == "__main__":
    main()
