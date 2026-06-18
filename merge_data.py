#!/usr/bin/env python3
"""
数据合并保护层：在 CI 环境中确保不丢失博主数据和灵感库。

问题：CI 环境没有抖音 Cookie，抓不到博主视频，generate_hot.py 的救援逻辑
     可能因为各种原因不生效，导致 data.json 缺少博主拆解和灵感库。

解决：在 generate_hot.py 运行后、gen_js_data.py 运行前，对比新旧数据，
     如果新数据缺少博主/灵感，从旧数据中补充。
"""
import json
import os
import sys
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def merge_data():
    """合并新旧数据，确保不丢失博主文章和灵感库"""

    # 1. 从 git 获取旧的 data.json（CI checkout 后的版本）
    old_data = None
    try:
        import subprocess
        r = subprocess.run(
            ["git", "show", "HEAD:data.json"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            old_data = json.loads(r.stdout)
            print(f"  📂 从 git 读取旧数据: {len(old_data.get('articles', []))} 条")
    except Exception as e:
        print(f"  ⚠️ 读取旧 git 数据失败: {e}")

    if not old_data:
        print("  ℹ️ 没有旧数据，跳过合并")
        return

    # 2. 读取新生成的 data.json
    new_data = load_json(DATA_FILE)
    if not new_data:
        print("  ❌ 新数据读取失败，跳过合并")
        return

    new_articles = new_data.get("articles", [])
    old_articles = old_data.get("articles", [])

    # 统计
    new_bloggers = [a for a in new_articles if a.get("source") == "blogger"]
    old_bloggers = [a for a in old_articles if a.get("source") == "blogger"]
    new_inspirations = new_data.get("inspirations", [])
    old_inspirations = old_data.get("inspirations", [])

    print(f"  📊 新数据: {len(new_articles)} 条文章, {len(new_bloggers)} 条博主, {len(new_inspirations)} 条灵感")
    print(f"  📊 旧数据: {len(old_articles)} 条文章, {len(old_bloggers)} 条博主, {len(old_inspirations)} 条灵感")

    merged = False

    # 3. 如果新数据缺少博主文章，从旧数据补充
    if len(new_bloggers) < 3 and len(old_bloggers) > 0:
        # 移除新数据中可能存在的不完整博主数据
        new_articles = [a for a in new_articles if a.get("source") != "blogger"]
        # 添加旧的博主数据
        new_articles.extend(old_bloggers)
        new_data["articles"] = new_articles
        merged = True
        print(f"  ✅ 补充 {len(old_bloggers)} 条旧博主数据")

    # 4. 如果新数据缺少灵感库，从旧数据补充
    if len(new_inspirations) < 10 and len(old_inspirations) > 0:
        new_data["inspirations"] = old_inspirations
        merged = True
        print(f"  ✅ 补充 {len(old_inspirations)} 条旧灵感数据")

    # 5. 确保 updated_at 存在
    if not new_data.get("updated_at"):
        new_data["updated_at"] = datetime.now().isoformat()
        merged = True

    # 6. 写回
    if merged:
        save_json(DATA_FILE, new_data)
        # 重新统计
        final_articles = new_data.get("articles", [])
        final_bloggers = [a for a in final_articles if a.get("source") == "blogger"]
        final_inspirations = new_data.get("inspirations", [])
        print(f"  📦 合并后: {len(final_articles)} 条文章, {len(final_bloggers)} 条博主, {len(final_inspirations)} 条灵感")
    else:
        print("  ℹ️ 数据完整，无需合并")


if __name__ == "__main__":
    merge_data()
