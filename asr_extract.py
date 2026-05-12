#!/usr/bin/env python3
"""批量 ASR：TikHub → 下载 → Whisper → 生成简介"""
import json, os, subprocess, time, whisper

KEY = "174GPMog11iQqEi0BtylwhDyBASfVcZJwkHalWSseeaLp1bhKnalUiunGQ=="
BASE = "https://api.tikhub.io"
WORK = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "C:/Users/Kevin/ffmpeg/ffmpeg-master-latest-win64-gpl-shared/bin/ffmpeg.exe"
TMP = os.path.join(WORK, "asr_temp")
os.makedirs(TMP, exist_ok=True)

def api_post(endpoint, params):
    bf = os.path.join(TMP, "_body.json")
    with open(bf, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False)
    for _ in range(3):
        try:
            r = subprocess.run(["curl","-s","-X","POST",f"{BASE}{endpoint}",
                "-H",f"Authorization: Bearer {KEY}",
                "-H","Content-Type: application/json; charset=utf-8",
                "-d",f"@{bf}","--connect-timeout","15","--max-time","25"],
                capture_output=True,text=True,timeout=30,encoding="utf-8",errors="replace")
            d = json.loads(r.stdout)
            if d.get("code") == 200:
                return d
        except: time.sleep(3)
    return None

def api_get(endpoint):
    for _ in range(3):
        try:
            r = subprocess.run(["curl","-s",f"{BASE}{endpoint}",
                "-H",f"Authorization: Bearer {KEY}",
                "--connect-timeout","15","--max-time","25"],
                capture_output=True,text=True,timeout=30,encoding="utf-8",errors="replace")
            d = json.loads(r.stdout)
            if d.get("code") in (200, None) and "aweme_list" in r.stdout:
                return d
        except: time.sleep(3)
    return None

def search_user(name):
    d = api_post("/api/v1/douyin/search/fetch_user_search_v2", {"keyword":name,"cursor":0})
    if not d: return None
    outer = d.get("data",{})
    inner = outer.get("data",{}) if isinstance(outer,dict) else {}
    users = inner.get("user_list",[]) if isinstance(inner,dict) else []
    if users:
        u = users[0].get("user_info", users[0])
        return u.get("user_id"), u.get("nick_name","")
    return None, None

def get_latest_video(sec_uid):
    d = api_get(f"/api/v1/douyin/app/v3/fetch_user_post_videos?sec_user_id={sec_uid}&max_cursor=0&count=1")
    if not d: return None, None
    videos = d.get("data",{}).get("aweme_list",[]) or d.get("aweme_list",[])
    if videos:
        v = videos[0]
        urls = v.get("video",{}).get("play_addr",{}).get("url_list",[])
        return (urls[0] if urls else None), v.get("desc","")
    return None, None

def asr_video(dl_url):
    mp4 = os.path.join(TMP, "_dl.mp4")
    wav = os.path.join(TMP, "_dl.wav")
    subprocess.run([FFMPEG,"-y","-i",dl_url,"-c","copy","-t","180",
        "-max_muxing_queue_size","1024",mp4],capture_output=True,timeout=60)
    if not os.path.exists(mp4): return None
    subprocess.run([FFMPEG,"-y","-i",mp4,"-ac","1","-ar","16000","-t","180",wav],
        capture_output=True,timeout=30)
    if not os.path.exists(wav): return None
    model = whisper.load_model("small")
    r = model.transcribe(wav, language="zh", fp16=False)
    text = r["text"].strip()
    for f in [mp4,wav]:
        try: os.remove(f)
        except: pass
    sentences = [s.strip() for s in text.replace("。","。\n").split("\n") if s.strip()]
    return "。".join(sentences[:4])[:400]

def main():
    with open("data.json","r",encoding="utf-8-sig") as f:
        d = json.load(f)
    bloggers = [a for a in d["articles"] if a.get("source")=="blogger"]
    names = list(dict.fromkeys(a.get("blogger_name","") for a in bloggers))
    print(f"\n抖音 ASR: {len(names)} 位博主\n")
    
    results = {}
    for i,name in enumerate(names):
        print(f"[{i+1}/{len(names)}] {name}")
        try:
            uid, real_name = search_user(name)
            if not uid:
                print(f"  ❌ 未找到\n")
                continue
            dl_url, desc = get_latest_video(uid)
            if not dl_url:
                print(f"  ❌ 无下载链接\n")
                continue
            print(f"  desc: {desc[:50]}")
            summary = asr_video(dl_url)
            if summary:
                results[name] = summary
                print(f"  ✅ {len(summary)}字: {summary[:100]}\n")
            else:
                print(f"  ⚠️ ASR失败，用desc\n")
                results[name] = desc
        except Exception as e:
            print(f"  ❌ {e}\n")
    
    updated = 0
    for a in d["articles"]:
        if a.get("source")=="blogger" and a.get("blogger_name","") in results:
            a["content_intro"] = results[a["blogger_name"]]
            updated += 1
    
    if updated:
        with open("data.json","w",encoding="utf-8") as f:
            json.dump(d,f,ensure_ascii=False)
        subprocess.run(["C:/Users/Kevin/AppData/Local/Programs/Python/Python311/python.exe",
                       "gen_js_data.py"], cwd=WORK)
    
    print(f"\n✅ {updated} 条已更新")
    for a in d["articles"]:
        if a.get("source")=="blogger":
            print(f"[{a['blogger_name']}] {a['content_intro'][:120]}")

if __name__=="__main__":
    main()
