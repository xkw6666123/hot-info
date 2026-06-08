#!/usr/bin/env python3
"""飞书通知：博主视频更新检测 & 推送"""
import json, urllib.request, os, sys

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/a93ecc6b-0ab2-402f-9c87-636da7f5622a"
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

def send_card(title, elements, color="blue"):
    """发送飞书卡片消息"""
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": color},
            "elements": elements
        }
    }
    req = urllib.request.Request(
        FEISHU_WEBHOOK,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return resp.get("code") == 0

def check_updates():
    """对比新旧数据，检测新视频"""
    # 加载当前数据（gen_js_data.py 已生成好）
    if not os.path.exists(DATA_FILE):
        return None

    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    bloggers = [a for a in articles if a.get("source") == "blogger"]

    if not bloggers:
        return None

    # 按博主分组
    from collections import defaultdict
    by_name = defaultdict(list)
    for b in bloggers:
        by_name[b["blogger_name"]].append(b)

    # 构建飞书卡片内容
    stats_text = f"热点 {len(articles)} 篇 · 博主 {len(bloggers)} 条 · 灵感 {len(data.get('inspirations',[]))} 条"
    
    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**📊 本次更新概览**\n{stats_text}"}},
        {"tag": "hr"},
    ]

    for name, vids in sorted(by_name.items()):
        # 取最新一条作为代表
        latest = sorted(vids, key=lambda x: x.get("date", "") + x.get("time", ""), reverse=True)[0]
        ci = latest.get("content_intro", "")
        ci_len = len(ci)
        ci_status = "✅ ASR完整" if ci_len > 200 else (f"⚠️ {ci_len}字" if ci_len > 0 else "❌ 无文案")
        
        video_lines = []
        for v in vids[:3]:
            likes = v.get("likes", 0)
            likes_str = f"{likes//10000}万" if likes >= 10000 else str(likes)
            video_lines.append(f"• {v['title'][:30]} | 👍{likes_str} | {v['date']} {v.get('time','')}")

        md = f"**{name}** ({len(vids)}条) | {ci_status}\n" + "\n".join(video_lines)
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": md}})

    # 加个链接
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "action",
        "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🔗 打开网站"},
            "url": "https://rediancha.online",
            "type": "primary"
        }]
    })

    return stats_text, elements

def notify():
    """主入口：发送飞书通知"""
    result = check_updates()
    if not result:
        print("无数据，跳过通知")
        return False

    stats_text, elements = result
    ok = send_card(f"🔥 热点信息差更新 — {stats_text.split('·')[0].strip()}", elements, "turquoise")
    if ok:
        print("✅ 飞书通知已发送")
    else:
        print("⚠️ 飞书通知发送失败")
    return ok

if __name__ == "__main__":
    notify()
