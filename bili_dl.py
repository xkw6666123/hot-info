# -*- coding: utf-8 -*-
"""B站音频免登录下载：curl_cffi(impersonate=chrome) + 访客 buvid3 设备cookie。

为什么不用 yt-dlp：yt-dlp 默认 TLS 指纹会被 B站 412 反爬拦截（并非"需要登录"）。
curl_cffi 模拟真实 Chrome 指纹 + 免费 buvid3 设备 cookie 即可稳定下载（实测 2026-08 通过）。
"""
import os, re, subprocess, shutil

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def download_audio(url, out_wav, max_sec=300):
    """下载 B站视频音频流到 16k 单声道 wav。成功返回 wav 路径，失败返回 None。"""
    m = re.search(r"(BV[0-9A-Za-z]{10})", url or "")
    if not m:
        return None
    bvid = m.group(1)

    from curl_cffi import requests as creq
    s = creq.Session(impersonate="chrome", headers={"User-Agent": UA})
    try:
        s.get("https://www.bilibili.com", timeout=15)  # 建立 buvid3 设备 cookie
    except Exception:
        pass

    try:
        view = s.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
                     headers={"Referer": f"https://www.bilibili.com/video/{bvid}"}, timeout=15).json()
        if view.get("code") != 0:
            print(f"  ❌ view API code={view.get('code')} {view.get('message')}")
            return None
        cid = view["data"]["cid"]
        pl = s.get(f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&fourk=0",
                   headers={"Referer": f"https://www.bilibili.com/video/{bvid}"}, timeout=15).json()
        if pl.get("code") != 0:
            print(f"  ❌ playurl code={pl.get('code')} {pl.get('message')}")
            return None
        audios = ((pl.get("data") or {}).get("dash") or {}).get("audio") or []
        if not audios:
            return None
        audio = max(audios, key=lambda a: a.get("bandwidth", 0))
        audio_url = audio.get("baseUrl") or audio.get("base_url") or ""
    except Exception as e:
        print(f"  ❌ 解析失败: {type(e).__name__}: {str(e)[:100]}")
        return None
    if not audio_url:
        return None

    os.makedirs(os.path.dirname(out_wav), exist_ok=True)
    try:
        r = s.get(audio_url, headers={"Referer": "https://www.bilibili.com", "User-Agent": UA}, timeout=60)
        if r.status_code != 200 or len(r.content) < 1000:
            print(f"  ❌ 下载失败 HTTP {r.status_code}")
            return None
        m4a = out_wav.replace(".wav", ".m4a")
        with open(m4a, "wb") as f:
            f.write(r.content)
    except Exception as e:
        print(f"  ❌ 下载异常: {type(e).__name__}: {str(e)[:100]}")
        return None

    subprocess.run([FFMPEG, "-y", "-i", m4a, "-ac", "1", "-ar", "16000", "-t", str(max_sec), out_wav],
                   capture_output=True, timeout=120)
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 2000:
        return out_wav
    return None
