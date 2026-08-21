# -*- coding: utf-8 -*-
"""抖音免登录下载：a_bogus 签名 + 匿名 ttwid 设备 cookie（无需登录、无需 DOUYIN_COOKIE）。

链路（实测 2026-08 通过）：
1. ttwid 官方接口注册匿名设备 cookie + 随机 msToken
2. aweme/v1/web/aweme/detail/?aweme_id=xxx 用 ABogus 签名 → aweme_detail.video
3. 音频地址在 video.bit_rate_audio[].audio_meta.url_list.main_url/backup_url（外部 CDN douyinvod.com）
4. 带 Referer 直接下载音频流 → ffmpeg 转 16k 单声道 wav
注意：播放地址带 dy_q 时间戳，有时效性（几分钟），须拿到后立即下载，不要缓存复用。
"""
import os, re, subprocess, shutil, random

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0")
COMMON = {
    "device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
    "update_version_code": "170400", "pc_client_type": "1", "pc_libra_divert": "Windows",
    "support_h265": "1", "support_dash": "0", "version_code": "290100", "version_name": "29.1.0",
    "cookie_enabled": "true", "screen_width": "1920", "screen_height": "1080",
    "browser_language": "zh-CN", "browser_platform": "Win32", "browser_name": "Edge",
    "browser_version": "130.0.0.0", "browser_online": "true", "engine_name": "Blink",
    "engine_version": "130.0.0.0", "os_name": "Windows", "os_version": "10",
    "cpu_core_num": "12", "device_memory": "8", "platform": "PC", "downlink": "10",
    "effective_type": "4g", "round_trip_time": "50",
}


class DouyinDL:
    def __init__(self):
        import requests as _req
        from douyin_abogus import ABogus, BrowserFingerprintGenerator
        self.session = _req.Session()
        self.session.headers.update({"User-Agent": WEB_UA})
        self.abogus = ABogus(user_agent=WEB_UA, fp=BrowserFingerprintGenerator.generate_fingerprint("Edge"))
        ttwid = ""
        try:
            r = self.session.post("https://ttwid.bytedance.com/ttwid/union/register/",
                                  json={"region": "cn", "aid": 1768, "needFid": False,
                                        "service": "https://www.douyin.com/", "mip": "0.0.0.0",
                                        "cbUrlProtocol": "https", "union": True},
                                  headers={"Content-Type": "application/json", "User-Agent": WEB_UA}, timeout=10)
            ttwid = r.cookies.get("ttwid") or ""
        except Exception:
            pass
        ms_token = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") for _ in range(107))
        self.cookie = "; ".join((["ttwid=" + ttwid] if ttwid else []) + ["msToken=" + ms_token, "odin_tt=1"])

    def _get(self, path, params):
        query = "&".join(f"{k}={v}" for k, v in params.items())
        signed, _ab, ua, _ = self.abogus.generate_abogus(query, "")
        return self.session.get(f"https://www.douyin.com{path}?{signed}",
                                headers={"User-Agent": ua, "Referer": "https://www.douyin.com/",
                                         "Cookie": self.cookie, "Accept": "application/json, text/plain, */*"},
                                timeout=15)

    @staticmethod
    def _audio_url_from_video(v):
        for item in (v.get("bit_rate_audio") or []):
            am = item.get("audio_meta") or {}
            ul = am.get("url_list") or {}
            for k in ("main_url", "backup_url"):
                if ul.get(k):
                    return ul[k]
        return ""

    def audio_url_by_aweme_id(self, aweme_id):
        """按 aweme_id 拿音频流地址（detail 接口）"""
        try:
            j = self._get("/aweme/v1/web/aweme/detail/", {**COMMON, "aweme_id": str(aweme_id)}).json()
            v = (j.get("aweme_detail") or {}).get("video") or {}
            return self._audio_url_from_video(v)
        except Exception:
            return ""

    def audio_url_by_sec_uid(self, sec_uid, count=30):
        """按博主 sec_uid 拿最新视频的音频地址映射 {aweme_id: audio_url}（post 接口）"""
        result = {}
        try:
            params = {**COMMON, "sec_user_id": sec_uid, "count": str(count), "max_cursor": "0",
                      "locate_query": "false", "publish_video_strategy_type": "2",
                      "need_time_list": "1", "time_list_query": "0", "whale_cut_token": "",
                      "cut_version": "1", "from_user_page": "1"}
            j = self._get("/aweme/v1/web/aweme/post/", params).json()
            for a in (j.get("aweme_list") or []):
                url = self._audio_url_from_video(a.get("video") or {})
                if url:
                    result[str(a.get("aweme_id"))] = url
        except Exception:
            pass
        return result

    def download_audio(self, audio_url, out_wav, max_sec=300):
        """下载音频流并转 16k 单声道 wav。成功返回 wav 路径，失败 None。"""
        try:
            r = self.session.get(audio_url, headers={"Referer": "https://www.douyin.com/",
                                                     "User-Agent": WEB_UA}, timeout=60)
            if r.status_code != 200 or len(r.content) < 1000:
                return None
            os.makedirs(os.path.dirname(out_wav), exist_ok=True)
            m4a = out_wav.replace(".wav", ".m4a")
            with open(m4a, "wb") as f:
                f.write(r.content)
            subprocess.run([FFMPEG, "-y", "-i", m4a, "-ac", "1", "-ar", "16000", "-t", str(max_sec), out_wav],
                           capture_output=True, timeout=120)
            if os.path.exists(out_wav) and os.path.getsize(out_wav) > 2000:
                return out_wav
        except Exception:
            pass
        return None
