#!/usr/bin/env python3
"""yt-dlp + Whisper：直接下载抖音音频 → ASR，绕过 Playwright"""
import json, os, subprocess, sys, re, hashlib, whisper as _whisper, shutil
from pathlib import Path

D_WHISPER = os.environ.get('D_WHISPER', r'D:\AI\whisper')
D_MODELS = os.path.join(D_WHISPER, 'models')
D_TEMP = os.path.join(D_WHISPER, 'asr_temp')
os.makedirs(D_TEMP, exist_ok=True)

FFMPEG = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe") or "ffmpeg"
YTDLP = shutil.which("yt-dlp") or "yt-dlp"

def load_whisper():
    for name in ['medium', 'small']:
        model_file = os.path.join(D_MODELS, f'{name}.pt')
        if os.path.exists(model_file):
            try:
                model = _whisper.load_model(model_file)
                print(f"  🎤 Whisper {name} 加载成功")
                return model
            except:
                continue
    try:
        return _whisper.load_model('small')
    except:
        return _whisper.load_model('medium')

def asr_video(video_url, tag=""):
    """yt-dlp 下载音频 → Whisper 转文字"""
    tag = tag or hashlib.md5(video_url.encode()).hexdigest()[:8]
    wav = os.path.join(D_TEMP, f"_yt_{tag}.wav")
    
    # 如果已存在结果，跳过
    out_log = wav + ".txt"
    if os.path.exists(out_log):
        with open(out_log, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        return text
    
    # yt-dlp 下载并转 wav
    try:
        cmd = [YTDLP, "--no-warnings", "--max-filesize", "200M", 
               "--extract-audio", "--audio-format", "wav",
               "--output", str(wav).replace('.wav', ''),  # yt-dlp 自动加扩展名
               video_url]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # yt-dlp 可能输出名为 .wav/.mp4 的文件
        found = []
        for ext in ['.wav', '.mp4', '.m4a', '.mp3']:
            p = str(wav).replace('.wav', ext)
            if os.path.exists(p) and os.path.getsize(p) > 1000:
                found.append(p)
                break
        
        if not found:
            # 尝试查找 yt-dlp 输出的实际文件名
            dir_list = os.listdir(D_TEMP)
            yt_files = [os.path.join(D_TEMP, f) for f in dir_list if f.endswith(('.wav', '.mp4', '.m4a'))]
            yt_files.sort(key=os.path.getmtime, reverse=True)
            found = yt_files[:1] if yt_files else []
        
        audio_file = found[0] if found else None
        if not audio_file:
            return ""
        
        # 如果不是 wav，转 wav
        if not audio_file.endswith('.wav'):
            subprocess.run([FFMPEG, "-y", "-i", audio_file, "-ac", "1", "-ar", "16000", wav],
                          capture_output=True, timeout=30)
            os.remove(audio_file)
            audio_file = wav
        
        if not os.path.exists(audio_file) or os.path.getsize(audio_file) < 1000:
            return ""
        
        # Whisper
        model = load_whisper()
        r = model.transcribe(audio_file, language="zh", fp16=False, verbose=False)
        text = r["text"].strip()
        
        # 清理
        try: os.remove(audio_file)
        except: pass
        
        if len(text) < 10:
            return ""
        
        # 中文占比检查
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese / max(len(text), 1) < 0.3:
            return ""
        
        # 保存缓存
        with open(out_log, 'w', encoding='utf-8') as f:
            f.write(text)
        
        return text
    except Exception as e:
        print(f"    ❌ yt-dlp/Whisper 失败: {type(e).__name__}: {e}")
        return ""

def main():
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    bloggers = [a for a in d["articles"] if a.get("source") == "blogger"]
    
    # 只处理没有 ASR 结果（>50字）的
    remaining = [a for a in bloggers if len(a.get("content_intro", "")) <= 50]
    print(f"\n🎯 yt-dlp ASR: {len(remaining)}/{len(bloggers)} 条需要处理\n")
    
    updated = 0
    for i, v in enumerate(remaining):
        url = v.get("url", "")
        name = v.get("blogger_name", "")
        title = (v.get("title") or "")[:30]
        
        print(f"[{i+1}/{len(remaining)}] {name} | {title}")
        
        # 生成摘要
        text = asr_video(url, tag=name[:4] + str(i))
        if not text:
            print(f"  ⚠️ 无有效转录")
            continue
        
        # 摘要
        events = re.split(r'(?=第[一二三四五六七八九十\d]+[件事个]|首先|另外|还有|接下来|最后|OK|下一件事)', text)
        if len(events) > 1:
            summary = "\n".join(f"  · {e.strip()[:80]}" for e in events[:6] if len(e.strip()) > 10)
        else:
            summary = text[:500]
        
        v["content_intro"] = summary
        updated += 1
        print(f"  ✅ {len(summary)}字")
    
    if updated:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        subprocess.run([sys.executable, "gen_js_data.py"], cwd=os.path.dirname(os.path.abspath(__file__)))
    
    print(f"\n✅ 更新 {updated}/{len(remaining)} 条")

if __name__ == "__main__":
    main()
