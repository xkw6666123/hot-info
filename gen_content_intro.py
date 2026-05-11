#!/usr/bin/env python3
"""
视频内容简介生成器（最终版）
规则：直接用视频 desc（作者原始文案）
- desc有实质内容的 → 直接展示
- desc等于标题 → 标注"视频描述"后展示话题标签
"""
import json


def generate_intro(v):
    desc = (v.get("summary") or v.get("title") or "").strip()
    title = (v.get("title") or "").strip()
    blogger = v.get("blogger_name", "")
    
    # 提取纯文本（去标签）和话题标签
    parts = desc.split("#")
    main_text = parts[0].strip()
    hashtags = [h.strip() for h in parts[1:] if h.strip()]
    
    # 有长描述（比如阿七的"三个有趣的生活小事件..."）
    if len(main_text) > 30 and main_text != title[:len(main_text)]:
        return desc
    
    # 描述就是标题本身
    if blogger in ("阿七大型纪录片", "信息黑板报", "沙漠一之雕"):
        if hashtags:
            return f"视频描述：{main_text}\n话题：{' #'.join(hashtags[:8])}"
        return f"视频描述：{main_text}"
    
    # 其他博主可能有更多内容
    if len(desc) > len(title) + 10:
        return desc  # 描述比标题长，展示完整版
    
    return desc


def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    count = 0
    for a in d["articles"]:
        if a.get("source") != "blogger":
            continue
        new_intro = generate_intro(a)
        if new_intro != a.get("content_intro", ""):
            a["content_intro"] = new_intro
            count += 1
    
    if count > 0:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    
    print(f"✅ {count} 条已更新\n")
    for a in d["articles"]:
        if a.get("source") == "blogger":
            print(f"[{a['blogger_name']}] {a.get('date','?')}")
            print(f"  {a['content_intro'][:120]}")
            print()


if __name__ == "__main__":
    main()
