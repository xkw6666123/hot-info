#!/usr/bin/env python3
"""
每条视频独立 ASR + 智能摘要
- 每个博主获取最新 N 条视频（= 数据里的条目数）
- 每条独立下载 + ASR
- 智能摘要：提取视频口播中的关键事件
"""
import json, os, subprocess, time, whisper, re

KEY = "174GPMog11iQqEi0BtylwhDyBASfVcZJwkHalWSseeaLp1bhKnalUiunGQ=="
BASE = "https://api.tikhub.io"
WORK = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "C:/Users/Kevin/ffmpeg/ffmpeg-master-latest-win64-gpl-shared/bin/ffmpeg.exe"
TMP = os.path.join(WORK, "asr_temp")
os.makedirs(TMP, exist_ok=True)

def api_call(method, endpoint, params=None):
    bf = os.path.join(TMP, "_b.json")
    if params:
        with open(bf, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False)
    for _ in range(3):
        try:
            if method == "POST":
                r = subprocess.run(["curl","-s","-X","POST",f"{BASE}{endpoint}",
                    "-H",f"Authorization: Bearer {KEY}",
                    "-H","Content-Type: application/json; charset=utf-8",
                    "-d",f"@{bf}","--connect-timeout","15","--max-time","25"],
                    capture_output=True,text=True,timeout=30,encoding="utf-8",errors="replace")
            else:
                r = subprocess.run(["curl","-s",f"{BASE}{endpoint}",
                    "-H",f"Authorization: Bearer {KEY}",
                    "--connect-timeout","15","--max-time","25"],
                    capture_output=True,text=True,timeout=30,encoding="utf-8",errors="replace")
            d = json.loads(r.stdout)
            if d.get("code") in (200, None) and "aweme_list" in r.stdout or method == "POST":
                return d
        except: time.sleep(2)
    return None

def search_user(name):
    d = api_call("POST", "/api/v1/douyin/search/fetch_user_search_v2", {"keyword":name,"cursor":0})
    if not d: return None
    outer = d.get("data",{})
    inner = outer.get("data",{}) if isinstance(outer,dict) else {}
    users = inner.get("user_list",[]) if isinstance(inner,dict) else []
    if users:
        u = users[0].get("user_info", users[0])
        return u.get("user_id"), u.get("nick_name","")
    return None, None

def get_videos(sec_uid, count=3):
    d = api_call("GET", f"/api/v1/douyin/app/v3/fetch_user_post_videos?sec_user_id={sec_uid}&max_cursor=0&count={count}")
    if not d: return []
    videos = d.get("data",{}).get("aweme_list",[]) or d.get("aweme_list",[])
    return [{"desc": v.get("desc",""), 
             "url": (v.get("video",{}).get("play_addr",{}).get("url_list",[None])[0]),
             "date": v.get("create_time",0),
             "likes": v.get("statistics",{}).get("digg_count",0)}
            for v in videos if v.get("video",{}).get("play_addr",{}).get("url_list")]

def download_asr(dl_url):
    mp4 = os.path.join(TMP, "_v.mp4")
    wav = os.path.join(TMP, "_v.wav")
    subprocess.run([FFMPEG,"-y","-i",dl_url,"-c","copy","-t","180",
        "-max_muxing_queue_size","1024",mp4],capture_output=True,timeout=60)
    if not os.path.exists(mp4): return ""
    subprocess.run([FFMPEG,"-y","-i",mp4,"-ac","1","-ar","16000","-t","180",wav],
        capture_output=True,timeout=30)
    if not os.path.exists(wav): return ""
    model = whisper.load_model("small")
    r = model.transcribe(wav, language="zh", fp16=False)
    text = r["text"].strip()
    for f in [mp4,wav]:
        try: os.remove(f)
        except: pass
    return text

def smart_summary(text, blogger=""):
    """智能摘要：提取视频中的关键事件"""
    if not text or len(text) < 10:
        return text
    
    # 去掉常见口头禅
    text = re.sub(r'然后|就是说|那个|这个|对吧|你知道吗|啊|嗯|哦', '', text)
    
    # 找"第X件""第一""首先""另外"等结构
    events = re.split(r'(?=第[一二三四五六七八九十\d]+[件事个]|首先|另外|还有|接下来|最后|其次)', text)
    
    if len(events) > 1:
        # 结构化的新闻视频：提取每个事件
        bullets = []
        for e in events[:6]:
            e = e.strip()
            if len(e) > 5:
                # 截取每个事件的核心（前20字）
                short = e[:80]
                if len(e) > 80:
                    short += "…"
                bullets.append(f"  · {short}")
        return "\n".join(bullets) if bullets else text[:250]
    
    # 无结构化：取开头 + 关键句
    sentences = [s.strip() for s in text.replace("。","。\n").split("\n") if s.strip()]
    if len(sentences) <= 3:
        return text[:250]
    
    # 取前2句 + 中间最长的1句
    best = sentences[:2]
    middle = sorted(sentences[2:], key=len, reverse=True)[:1]
    return "。".join(best + middle)[:300]

def main():
    with open("data.json","r",encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d["articles"] if a.get("source")=="blogger"]
    
    # 按博主分组
    from collections import defaultdict
    groups = defaultdict(list)
    for a in bloggers:
        groups[a.get("blogger_name","")].append(a)
    
    print(f"\n{'='*50}")
    print(f"ASR: {len(groups)} 位博主，{len(bloggers)} 条视频")
    print(f"{'='*50}\n")
    
    updated = 0
    for name, entries in groups.items():
        print(f"\n[{name}] {len(entries)} 条视频")
        
        # B站跳过（单独处理）
        if all("bilibili.com" in (e.get("url") or "") for e in entries):
            print("  B站视频，跳过")
            continue
        
        try:
            uid, real_name = search_user(name if name != "信息黑板报" else "信息黑板报")
            if not uid:
                print(f"  ❌ 未找到用户")
                continue
            
            # 获取最新 N 条视频
            videos = get_videos(uid, count=len(entries))
            print(f"  获取到 {len(videos)} 条视频")
            
            for i, (entry, vinfo) in enumerate(zip(entries, videos)):
                print(f"  [{i+1}/{len(entries)}] {vinfo['desc'][:40]}...")
                transcript = download_asr(vinfo['url'])
                if transcript:
                    summary = smart_summary(transcript, name)
                    old = entry.get("content_intro","")
                    if summary != old:
                        entry["content_intro"] = summary
                        updated += 1
                        print(f"    ✅ {len(summary)}字")
                else:
                    print(f"    ❌ ASR失败，保留原文案")
        except Exception as e:
            print(f"  ❌ {e}")
    
    if updated:
        with open("data.json","w",encoding="utf-8") as f:
            json.dump(d,f,ensure_ascii=False)
        subprocess.run(["C:/Users/Kevin/AppData/Local/Programs/Python/Python311/python.exe",
                       "gen_js_data.py"], cwd=WORK)
    
    print(f"\n{'='*50}")
    print(f"✅ {updated} 条视频内容已更新")
    
    for a in d["articles"]:
        if a.get("source")=="blogger":
            intro = a.get("content_intro","")
            print(f"\n[{a['blogger_name']}] {a.get('date','?')}")
            print(f"  {intro[:150]}")

if __name__=="__main__":
    main()
