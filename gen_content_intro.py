#!/usr/bin/env python3
"""
为缺少 content_intro 的博主视频生成内容简介
基于标题+分析数据+博主风格生成自然语言概括
"""
import json

def generate_intro(v):
    """基于视频元数据生成内容简介"""
    a = v.get("analysis", {})
    title = v.get("title", "")
    blogger = v.get("blogger_name", "")
    kw = a.get("keywords", [])
    tip = a.get("replicable_tip", "")
    summary = v.get("summary", "")
    
    # 去掉标题中的hashtags，取主体
    clean_title = title.split("#")[0].strip()
    
    # 如果summary比标题长且不是纯hashtags，优先用summary
    clean_summary = summary.split("#")[0].strip() if summary else ""
    
    # 按博主类型生成不同风格的简介
    if "网吧信息差" in blogger:
        topic = clean_title if len(clean_title) > 5 else "社会热点"
        return (
            f"本期视频以大学生视角切入，标题「{topic}」制造反差悬念。"
            f"内容围绕信息差展开，揭露社会热点或离谱现象的内幕，"
            f"配合土嗨BGM和游戏音效转场，节奏紧凑有趣，"
            f"用大学生日常做切入制造共鸣。"
        )
    elif "阿七大型纪录片" in blogger:
        topic = clean_title if len(clean_title) > 5 else "当日热点"
        return (
            f"日更社会热点信息差系列，以日期锚点「{topic}」命名。"
            f"内容涵盖3-5条当日热搜社会新闻和民生话题，"
            f"采用快节奏新闻播报式剪辑，30秒内完成信息传递，"
            f"帮助观众3分钟掌握全网信息差。"
        )
    elif "陈先生" in blogger:
        topic = clean_title if len(clean_title) > 5 else "社会热点"
        return (
            f"大型纪录片风格的热点深度解构视频，「{topic}」以悬念式开场。"
            f"深入拆解社会事件的来龙去脉，从信息差视角剖析其中的反转和争议，"
            f"低沉解说配合纪录片质感画面，层层递进揭露事件真相。"
        )
    elif "信息黑板报" in blogger:
        topic = clean_title if len(clean_title) > 5 else "当日热点"
        return (
            f"社会热点信息差合集系列，「{topic}」。"
            f"精选当日民生和社会类热点新闻，每条以简短点评式快讯呈现核心信息，"
            f"结尾引导点赞收藏，帮助用户快速获取当日要闻。"
        )
    elif "人类观察菌" in blogger:
        topic = clean_title if len(clean_title) > 5 else "迷惑行为"
        return (
            f"人类迷惑行为大赏系列，「{topic}」。"
            f"精选当日逆天离谱的新闻和社交热点，以沙雕搞笑风格剪辑呈现，"
            f"用#逆天 #离谱 #迷惑人类等标签引流，让观众在娱乐中获取信息差。"
        )
    elif "沙漠一之雕" in blogger:
        topic = clean_title if len(clean_title) > 5 else "热搜话题"
        return (
            f"B站日更热点快报系列，「{topic}」。"
            f"精选当日热搜话题制作搞笑合集，配沙雕BGM和标题党封面，"
            f"1分钟内快速浏览热点，用神转折剪辑和搞笑配音保持观看趣味性。"
        )
    else:
        kw_str = "、".join(kw[:3]) if kw else "热点"
        return f"本期视频主题为「{clean_title}」，围绕{kw_str}等关键词展开。{tip}"


def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    count = 0
    for a in d["articles"]:
        if a.get("source") == "blogger":
            # 已有 content_intro 的跳过（保留之前的真实内容）
            if a.get("content_intro"):
                continue
            a["content_intro"] = generate_intro(a)
            count += 1
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    
    print(f"已为 {count} 条博主视频生成内容简介")
    for a in d["articles"]:
        if a.get("source") == "blogger":
            print(f"  [{a['blogger_name']}] {a['content_intro'][:80]}...")


if __name__ == "__main__":
    main()
