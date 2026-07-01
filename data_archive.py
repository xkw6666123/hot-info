#!/usr/bin/env python3
"""
数据归档系统：确保热点数据不丢失
每次运行时将当前数据归档到 data_archive.json
"""
import json
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
ARCHIVE_FILE = os.path.join(BASE_DIR, "data_archive.json")


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


def archive_data():
    """归档当前数据"""
    current = load_json(DATA_FILE)
    if not current:
        print("  ⚠️ 无数据可归档")
        return

    archive = load_json(ARCHIVE_FILE) or {"articles": [], "last_archived": None}

    # 获取当前文章
    current_articles = current.get("articles", [])
    archive_articles = archive.get("articles", [])

    # 按ID去重，保留最新的
    seen_ids = set()
    merged = []

    # 先添加归档中的文章
    for a in archive_articles:
        aid = a.get("id")
        if aid and aid not in seen_ids:
            seen_ids.add(aid)
            merged.append(a)

    # 再添加当前文章（更新或新增）
    for a in current_articles:
        aid = a.get("id")
        if aid:
            if aid in seen_ids:
                # 替换旧的
                merged = [m for m in merged if m.get("id") != aid]
            merged.append(a)
            seen_ids.add(aid)

    # 只保留近14天的数据
    cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    merged = [a for a in merged if a.get("date", "") >= cutoff]

    archive["articles"] = merged
    archive["last_archived"] = datetime.now().isoformat()

    save_json(ARCHIVE_FILE, archive)
    print(f"  📦 归档完成: {len(merged)} 条文章 (当前: {len(current_articles)} 条)")


def restore_from_archive():
    """从归档恢复数据"""
    current = load_json(DATA_FILE)
    archive = load_json(ARCHIVE_FILE)

    if not current or not archive:
        print("  ⚠️ 无数据可恢复")
        return

    current_articles = current.get("articles", [])
    archive_articles = archive.get("articles", [])

    # 按ID去重
    current_ids = set(a.get("id") for a in current_articles)
    restored = 0

    for a in archive_articles:
        if a.get("id") not in current_ids:
            current_articles.append(a)
            restored += 1

    if restored:
        current["articles"] = current_articles
        save_json(DATA_FILE, current)
        print(f"  ✅ 从归档恢复 {restored} 条文章")
    else:
        print("  ℹ️ 无需恢复")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_from_archive()
    else:
        archive_data()
