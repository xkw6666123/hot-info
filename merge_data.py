#!/usr/bin/env python3
"""
数据合并保护层：在 CI 环境中确保不丢失博主数据、灵感库和 ASR 文案。

核心机制：
- ASR 文案存储在独立的 asr_content.json 中（不受 CI 数据覆盖）
- merge_data.py 在每次数据生成后运行，从 asr_content.json 迁移文案
- 本地 auto_run.bat 也会更新 asr_content.json
"""
import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
ASR_FILE = os.path.join(BASE_DIR, "asr_content.json")


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


def update_asr_backup(data):
    """把 data.json 中的完整 ASR 文案同步到 asr_content.json"""
    asr_backup = load_json(ASR_FILE) or {}
    articles = data.get("articles", [])
    updated = 0
    for a in articles:
        if a.get("source") != "blogger":
            continue
        ci = a.get("content_intro", "")
        if len(ci) < 100:
            continue
        key = a.get("aweme_id", "") or a.get("url", "") or str(a.get("id", ""))
        if not key:
            continue
        existing = asr_backup.get(key, {})
        # 只更新更长的文案
        if len(ci) > len(existing.get("content_intro", "")):
            asr_backup[key] = {
                "content_intro": ci,
                "blogger_name": a.get("blogger_name", ""),
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "aweme_id": a.get("aweme_id", ""),
            }
            updated += 1
    if updated:
        save_json(ASR_FILE, asr_backup)
        print(f"  💾 更新 asr_content.json: +{updated} 条 (共 {len(asr_backup)} 条)")
    return asr_backup


def restore_asr_content(data, asr_backup):
    """从 asr_content.json 恢复 ASR 文案到 data.json"""
    if not asr_backup:
        return 0
    articles = data.get("articles", [])
    restored = 0
    for a in articles:
        if a.get("source") != "blogger":
            continue
        ci = a.get("content_intro", "")
        if len(ci) >= 100:
            continue  # 已有完整文案
        # 按 aweme_id 和 URL 匹配
        for key in [a.get("aweme_id", ""), a.get("url", ""), str(a.get("id", ""))]:
            if key and key in asr_backup:
                backup_ci = asr_backup[key].get("content_intro", "")
                if len(backup_ci) > len(ci):
                    a["content_intro"] = backup_ci
                    restored += 1
                    break
    return restored


def merge_data():
    """合并新旧数据，确保不丢失博主文章、灵感库和 ASR 文案"""

    # 1. 读取新生成的 data.json
    new_data = load_json(DATA_FILE)
    if not new_data:
        print("  ❌ 新数据读取失败，跳过合并")
        return

    # 2. 从 git 获取旧的 data.json（用于补充博主和灵感）
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

    # 3. 加载 ASR 文案备份
    asr_backup = load_json(ASR_FILE) or {}
    print(f"  📂 ASR 文案备份: {len(asr_backup)} 条")

    new_articles = new_data.get("articles", [])
    new_bloggers = [a for a in new_articles if a.get("source") == "blogger"]
    new_inspirations = new_data.get("inspirations", [])

    print(f"  📊 新数据: {len(new_articles)} 条文章, {len(new_bloggers)} 条博主, {len(new_inspirations)} 条灵感")

    merged = False

    # 4. 从 ASR 备份恢复文案（核心：不受 CI 覆盖影响）
    restored = restore_asr_content(new_data, asr_backup)
    if restored:
        merged = True
        print(f"  ✅ 从 ASR 备份恢复 {restored} 条文案")

    # 5. 从旧数据补充缺失的博主文章
    # 核心逻辑：新数据中博主数量 < 旧数据中博主数量 → 补充旧数据
    # 这解决了 CI Cookie 过期导致抓不到部分博主的问题
    if old_data:
        old_articles = old_data.get("articles", [])
        old_bloggers = [a for a in old_articles if a.get("source") == "blogger"]
        new_blogger_names = set(b.get("blogger_name", "") for b in new_bloggers)
        old_blogger_names = set(b.get("blogger_name", "") for b in old_bloggers)
        missing_names = old_blogger_names - new_blogger_names
        
        # 也检查每个博主的视频数量是否减少
        from collections import Counter
        new_counts = Counter(b.get("blogger_name", "") for b in new_bloggers)
        old_counts = Counter(b.get("blogger_name", "") for b in old_bloggers)
        for name in old_blogger_names:
            if name in new_blogger_names:
                if old_counts[name] > new_counts[name]:
                    missing_names.add(name)
        
        if missing_names:
            # 新数据缺少部分博主或视频数量减少，用旧数据补充
            new_articles = [a for a in new_articles if a.get("source") != "blogger"]
            # 新数据中的博主保留
            new_articles.extend(new_bloggers)
            # 补充旧数据中缺失的博主
            for b in old_bloggers:
                if b.get("blogger_name", "") in missing_names:
                    # 避免重复
                    aweme_id = b.get("aweme_id", "")
                    if not any(x.get("aweme_id") == aweme_id for x in new_articles):
                        new_articles.append(b)
            new_data["articles"] = new_articles
            merged = True
            print(f"  ✅ 补充缺失博主: {', '.join(missing_names)}")
            # 再次恢复 ASR 文案
            restore_asr_content(new_data, asr_backup)

    # 6. 从旧数据补充灵感库
    # 如果新数据灵感字段为空或数量不足，用旧数据补充
    if old_data:
        old_inspirations = old_data.get("inspirations", [])
        # 检查新灵感是否有内容
        new_insp_has_content = any(
            len(i.get("wangba", "")) > 10 for i in new_inspirations[:3]
        ) if new_inspirations else False
        old_insp_has_content = any(
            len(i.get("wangba", "")) > 10 for i in old_inspirations[:3]
        ) if old_inspirations else False
        
        if (len(new_inspirations) < 10 or not new_insp_has_content) and old_insp_has_content:
            new_data["inspirations"] = old_inspirations
            merged = True
            print(f"  ✅ 补充 {len(old_inspirations)} 条旧灵感数据")

    # 7. 确保 updated_at 存在
    if not new_data.get("updated_at"):
        new_data["updated_at"] = datetime.now().isoformat()
        merged = True

    # 8. 写回
    if merged:
        save_json(DATA_FILE, new_data)
        final_articles = new_data.get("articles", [])
        final_bloggers = [a for a in final_articles if a.get("source") == "blogger"]
        final_inspirations = new_data.get("inspirations", [])
        short_ci = [b for b in final_bloggers if len(b.get("content_intro", "")) < 100]
        print(f"  📦 合并后: {len(final_articles)} 条文章, {len(final_bloggers)} 条博主, {len(final_inspirations)} 条灵感")
        if short_ci:
            print(f"  ⚠️ {len(short_ci)} 条博主文案仍较短（新视频，本地ASR未处理）")
    else:
        print("  ℹ️ 数据完整，无需合并")

    # 9. 更新 ASR 备份（把新的完整文案同步到 asr_content.json）
    update_asr_backup(new_data)


if __name__ == "__main__":
    merge_data()
