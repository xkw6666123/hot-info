#!/usr/bin/env python3
"""
视频内容简介生成器
规则：只用真实数据，绝不生成模板文案
- desc 有实质内容（>30字且不=标题）→ 直接使用
- desc 只有标题+话题 → 保留话题部分
- 没有任何有效描述 → 留空，等待 ASR 提取
"""
import json


def generate_intro(v):
    desc = (v.get("summary") or v.get("title") or "").strip()
    title = (v.get("title") or "").strip()
    
    # 提取纯文本和话题标签
    parts = desc.split("#")
    main_text = parts[0].strip()
    hashtags = [h.strip() for h in parts[1:] if h.strip()]
    
    # 有实质性长描述（排除纯标题的情况）
    if len(main_text) > 30 and main_text != title[:len(main_text)]:
        return desc
    
    # 只有标题+话题：把话题作为补充信息
    if hashtags:
        tags_str = " #".join(hashtags[:8])
        return f"{main_text}\n话题：#{tags_str}"
    
    # 什么都没有：留空等 ASR
    return ""


def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    count = 0
    for a in d["articles"]:
        if a.get("source") != "blogger":
            continue
        
        new_intro = generate_intro(a)
        old_intro = a.get("content_intro", "")
        
        # 已有真实 ASR 结果 → 永远不覆盖
        if old_intro and len(old_intro) > 80:
            continue
        
        # 新生成的太短 → 不写入，留空等 ASR
        if len(new_intro) < 80:
            continue
        
        # 写入有实质内容的新文案
        if new_intro and new_intro != old_intro:
            a["content_intro"] = new_intro
            count += 1
    
    if count > 0:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    
    print(f"✅ {count} 条已更新\n")
    for a in d["articles"]:
        if a.get("source") == "blogger":
            ci = a.get("content_intro", "")
            status = f"({len(ci)}字)" if ci else "(空-等ASR)"
            print(f"[{a['blogger_name']}] {a.get('date','?')} {status}")
            if ci:
                print(f"  {ci[:120]}")
            print()


if __name__ == "__main__":
    main()
