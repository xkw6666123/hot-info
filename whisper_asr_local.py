#!/usr/bin/env python3
"""
本地 Whisper ASR 流水线（无需任何 API key）：
1. 抖音：分享页同步解析（免 Playwright）→ 播放地址 → ffmpeg 转 16k wav
2. B站：yt-dlp 下载音频 → 16k wav
3. whisper base 转写（中文，繁转简）
4. 写回 data.json 的 content_intro（1:1 完整转录，不截断）

支持断点续跑：已完成（>=200字）的自动跳过。
"""
import json, os, re, subprocess, sys, time, shutil

WORK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORK)
os.chdir(WORK)

DT_PATH = r"D:\AI\hotinfo\douyin-transcribe"
if os.path.isdir(DT_PATH):
    sys.path.insert(0, DT_PATH)

DATA_FILE = os.path.join(WORK, "data.json")
TEMP = os.path.join(WORK, "asr_temp")
os.makedirs(TEMP, exist_ok=True)
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
MIN_LEN = 200
MAX_AUDIO_SEC = 300  # 前5分钟

# 繁简转换
try:
    from opencc import OpenCC
    _CC = OpenCC("t2s")
except Exception:
    _CC = None

_MODEL = None
_MODEL_KIND = None
_PUNC = None  # 标点模型（SenseVoice 输出无标点，需单独补）

def get_model():
    """转写引擎：SenseVoiceSmall（阿里最新，准确率高，免费本地已缓存）优先；
    seaco paraformer 兜底；whisper base 最后兜底。"""
    global _MODEL, _MODEL_KIND, _PUNC
    if _MODEL is None:
        try:
            from funasr import AutoModel
            _MODEL = AutoModel(
                model="iic/SenseVoiceSmall",
                trust_remote_code=True,
                disable_update=True,
            )
            _MODEL_KIND = "sensevoice"
            # SenseVoice 输出无标点，同时加载标点模型
            try:
                _PUNC = AutoModel(
                    model="iic/punc_ct-transformer_cn-en-common-vocab471067-large",
                    disable_update=True,
                )
            except Exception:
                _PUNC = None
            print("  ✅ SenseVoiceSmall 模型就绪（准确率更高）")
        except Exception as e:
            print(f"  ⚠️ SenseVoice 不可用({type(e).__name__})，降级 seaco paraformer")
            try:
                from funasr import AutoModel
                _MODEL = AutoModel(
                    model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                    vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                    punc_model="iic/punc_ct-transformer_cn-en-common-vocab471067-large",
                    disable_update=True,
                )
                _MODEL_KIND = "funasr"
                print("  ✅ funasr seaco 模型就绪")
            except Exception as e2:
                print(f"  ⚠️ funasr 不可用({type(e2).__name__})，降级 whisper base")
                import whisper
                print("  ⏳ 加载 whisper base 模型...")
                _MODEL = whisper.load_model("base")
                _MODEL_KIND = "whisper"
                print("  ✅ 模型就绪")
    return _MODEL


def transcribe(wav_path):
    model = get_model()
    if _MODEL_KIND == "sensevoice":
        res = model.generate(input=wav_path, language="zh", use_itn=False)
        text = (res[0]["text"] if res else "").strip()
        # 清洗 SenseVoice 特殊标签 <|zh|> <|HAPPY|> <|BGM|> <|woitn|> 等
        text = re.sub(r"<\|[^|]*\|>", "", text).strip()
        # 补标点（SenseVoice 输出无标点）
        if _PUNC:
            try:
                pres = _PUNC.generate(input=text)
                text = (pres[0]["text"] if pres else text).strip()
            except Exception:
                pass
    elif _MODEL_KIND == "funasr":
        res = model.generate(input=wav_path, batch_size_s=300)
        text = (res[0]["text"] if res else "").strip()
    else:
        r = model.transcribe(
            wav_path, language="zh", fp16=False,
            initial_prompt="以下是简体中文口语视频文案，包含网络流行语。",
            condition_on_previous_text=False,
        )
        text = (r.get("text") or "").strip()
    if _CC:
        text = _CC.convert(text)
    return text


def ffmpeg_wav(src_url_or_path, tag, referer=None):
    wav = os.path.join(TEMP, f"w_{tag}.wav")
    cmd = [FFMPEG, "-y"]
    if referer:
        cmd += ["-headers", f"Referer: {referer}\r\n"]
    cmd += ["-i", src_url_or_path, "-ac", "1", "-ar", "16000", "-t", str(MAX_AUDIO_SEC), wav]
    subprocess.run(cmd, capture_output=True, timeout=180)
    if not (os.path.exists(wav) and os.path.getsize(wav) > 2000):
        # 无 referer 重试
        subprocess.run([FFMPEG, "-y", "-i", src_url_or_path, "-ac", "1", "-ar", "16000",
                        "-t", str(MAX_AUDIO_SEC), wav], capture_output=True, timeout=180)
    if os.path.exists(wav) and os.path.getsize(wav) > 2000:
        return wav
    return None


def get_douyin_audio(url, tag):
    """抖音免登录：douyin_dl（a_bogus 签名）按 aweme_id 拿音频流 → wav"""
    import re as _re
    import douyin_dl
    m = _re.search(r"video/(\d+)", url or "")
    if not m:
        return None
    aweme_id = m.group(1)
    dl = douyin_dl.DouyinDL()
    audio_url = dl.audio_url_by_aweme_id(aweme_id)
    if not audio_url:
        print("    ❌ 无音频地址")
        return None
    wav = os.path.join(TEMP, f"w_{tag}.wav")
    return dl.download_audio(audio_url, wav, max_sec=MAX_AUDIO_SEC)


def get_bilibili_audio(url, tag):
    import bili_dl
    wav = os.path.join(TEMP, f"w_{tag}.wav")
    return bili_dl.download_audio(url, wav, max_sec=MAX_AUDIO_SEC)


def clean_text(t):
    t = re.sub(r"\s+", "", t or "")
    # 去掉 whisper 常见的语气助词堆叠开头
    return t.strip()


def main():
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    bloggers = [a for a in data.get("articles", []) if a.get("source") == "blogger"]
    need = [a for a in bloggers if len(a.get("content_intro") or "") < MIN_LEN]
    print(f"🎯 需补提文案: {len(need)}/{len(bloggers)} 条\n")
    if not need:
        print("✅ 全部完整")
        return

    done = 0
    for i, v in enumerate(need):
        name = v.get("blogger_name", "?")
        title = (v.get("title") or "")[:28]
        url = v.get("url", "")
        tag = v.get("aweme_id") or str(v.get("id", i))
        print(f"[{i+1}/{len(need)}] {name} | {title}")
        t0 = time.time()
        try:
            if "douyin.com" in url:
                wav = get_douyin_audio(url, tag)
            elif "bilibili.com" in url:
                wav = get_bilibili_audio(url, tag)
            else:
                print("    ⚠️ 未知平台，跳过")
                continue
            if not wav:
                continue
            text = clean_text(transcribe(wav))
            try:
                os.remove(wav)
            except OSError:
                pass
            if len(text) < 20:
                print(f"    ⚠️ 转写过短({len(text)}字)")
                continue
            v["content_intro"] = text
            done += 1
            print(f"    ✅ {len(text)}字 ({time.time()-t0:.0f}s): {text[:50]}...")
            # 每条都即时保存，防中断丢失
            with open(DATA_FILE + ".tmp", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(DATA_FILE + ".tmp", DATA_FILE)
        except Exception as e:
            print(f"    ❌ {type(e).__name__}: {str(e)[:150]}")

    print(f"\n✅ 完成 {done}/{len(need)} 条")


if __name__ == "__main__":
    main()
