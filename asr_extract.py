#!/usr/bin/env python3
"""免费 ASR：Playwright 拦截音频 → ffmpeg下载 → Whisper → 摘要"""
import json, os, subprocess, time, re, sys, shutil, hashlib
import whisper as _whisper

# 繁简转换
try:
    from opencc import OpenCC
    _CC = OpenCC('t2s')  # 繁体→简体
except Exception:
    _CC = None
D_WHISPER = os.environ.get('D_WHISPER', r'D:\AI\whisper')
D_MODELS = os.path.join(D_WHISPER, 'models')
D_TEMP = os.path.join(D_WHISPER, 'asr_temp')
os.makedirs(D_MODELS, exist_ok=True)
os.makedirs(D_TEMP, exist_ok=True)
TMP = D_TEMP
WORK = os.path.dirname(os.path.abspath(__file__))
FFMPEG = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe") or "ffmpeg"
PCLI = "playwright-cli"

# Whisper 模型全局单例（只加载一次，优先 medium，内存不够用 small）
# 直接传 .pt 文件路径，绕过 WHISPER_CACHE_DIR 的 checksum 校验
_WHISPER_MODEL = None
_WHISPER_NAME = None  # 记录实际加载的模型名称（用于 device）

def get_whisper():
    global _WHISPER_MODEL, _WHISPER_NAME
    if _WHISPER_MODEL is None:
        for name in ['medium', 'small']:
            model_file = os.path.join(D_MODELS, f'{name}.pt')
            if os.path.exists(model_file):
                try:
                    # 传文件路径而非名称，跳过 SHA256 校验
                    _WHISPER_MODEL = _whisper.load_model(model_file)
                    _WHISPER_NAME = name
                    print(f"  Whisper {name} 加载成功: {model_file}")
                    return _WHISPER_MODEL
                except Exception as e:
                    print(f"  Whisper {name} 加载失败，回退: {e}")
                    continue

        # 兜底：让 whisper 自动下载（medium 优先）
        try:
            _WHISPER_MODEL = _whisper.load_model('medium')
            _WHISPER_NAME = 'medium'
            print("  Whisper medium 加载成功（自动下载）")
        except Exception:
            _WHISPER_MODEL = _whisper.load_model('small')
            _WHISPER_NAME = 'small'
            print("  Whisper small 加载成功（回退）")
    return _WHISPER_MODEL

def _kill_playwright():
    """完全关闭 Playwright 浏览器，确保状态干净"""
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} kill-all"],
                   capture_output=True, timeout=10)
    time.sleep(1)

# ═══ 文本清洗 ═══
# Whisper 常见误识别 → 正确词
_WHISPER_FIXES = {
    '虎帐': 'coser',
    '虎帐优人': 'coser',
    '虎帐办演者': 'cosplay表演者',
    '炼铜皮': '恋童癖',
    '无警广员支队银门哨兵': '武警执勤',
    '黑闪酒机': '黑闪连击',
    '枪都已经向堂了': '枪都已经上膛了',
    '拒留': '拘留',
    '罩人男子': '肇事男子',
    '首部受伤': '头部受伤',
    '毒瘤女孩': '失明女孩',
    '将警快核实': '将尽快核实',
    '全之龙': '权志龙',
    '其不来的': '起不来的',
    '图件进攻': '推荐进攻',
    '彼此根': '培根',
    '鲜耳朵': '馅儿多',
    '鲜耳朵皮': '馅儿多的皮',
}

_NOISE_PATTERNS = [
    r'互联网宗教.*?许可证',
    r'药品医疗.*?备案',
    r'互联网新闻.*?许可证',
    r'网上有害信息举报',
    r'违法和不良.*?举报.*?\d+',
    r'算法推荐.*?举报',
    r'网络内容从业人员.*?举报',
    r'体育饭圈.*?举报',
    r'ICP备\d+',
    r'公网安备\d+',
    r'经营许可证',
    r'网络文化经营',
    r'增值电信',
    r'广播电视节目制作',
    r'^\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}',   # 时间戳
    r'^因浏览器限制.*静音',
    r'^作者声明',
    r'^发布时间',
    r'^请先登录后发表评论',
    r'^@\S+',                                    # @username
    r'^\d+条评论',
    r'^展开$',
    r'^收起$',
    r'^\.{3,}$',                                 # 纯省略号
]

def _clean_text(text):
    """清洗文本：繁体→简体、去备案与UI噪音、去除过短行"""
    if not text:
        return text
    
    # 繁体→简体
    if _CC:
        try:
            text = _CC.convert(text)
        except Exception:
            pass
    
    # Whisper 常见误识别修复
    for wrong, right in _WHISPER_FIXES.items():
        text = text.replace(wrong, right)
    
    lines = [l.strip() for l in text.split('\n')]
    clean = []
    for line in lines:
        if not line or len(line) < 3:
            continue
        skip = False
        for pat in _NOISE_PATTERNS:
            if re.search(pat, line):
                skip = True
                break
        if not skip:
            clean.append(line)
    
    return '\n'.join(clean).strip()

def get_audio_url(video_url, expected_aweme_id=""):
    """Playwright 打开视频页，从网络请求中截获音频 URL
    返回 (audio_url, response_html_len) 或 (None, 0)
    expected_aweme_id: 用于验证截获的音频是否属于当前视频
    """
    _kill_playwright()
    
    # 打开页面，用 longer wait + retry if page fails to load
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} open \"{video_url}\""],
                capture_output=True, timeout=30, text=True, encoding="utf-8", errors="replace"
            )
            break
        except subprocess.TimeoutExpired:
            if attempt < 2:
                _kill_playwright()
                time.sleep(3)
    
    time.sleep(7)  # 给页面足够时间加载和发起音频请求
    
    # 获取网络请求列表
    r = subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} requests"],
                       capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
    
    requests_output = r.stdout
    
    # 找到 audio URL (media-audio-und-mp4a)，验证是否包含当前视频的 aweme_id
    import urllib.parse
    
    best_audio = None
    
    for line in requests_output.split("\n"):
        if "media-audio-und-mp4a" in line and "douyinvod.com" in line:
            parts = line.split("=>")
            for part in parts:
                if "douyinvod.com" in part:
                    url_raw = part.strip().split(" ")[-1].strip("[]")
                    url = urllib.parse.unquote(url_raw)
                    # 验证 audio URL 是否与期望视频匹配
                    if expected_aweme_id and expected_aweme_id in url:
                        _kill_playwright()
                        return url
                    # 记录第一个找到的 audio URL 作为备选
                    if not best_audio:
                        best_audio = url
    
    # 如果有备选 audio URL（不匹配 aweme_id 但可能是正确的），返回它
    if best_audio:
        _kill_playwright()
        return best_audio
    
    # 如果没找到音频，找 video URL（MP4，后续用 ffmpeg 提取音频）
    for line in requests_output.split("\n"):
        if "media-video-avc1" in line and "douyinvod.com" in line:
            parts = line.split("=>")
            for part in parts:
                if "douyinvod.com" in part:
                    url_raw = part.strip().split(" ")[-1].strip("[]")
                    url = urllib.parse.unquote(url_raw)
                    _kill_playwright()
                    return url
    
    _kill_playwright()
    return None

# 全局去重：记录已处理的音频 URL，防止跨视频复用
_SEEN_AUDIO_URLS = set()

def download_asr(audio_url, video_tag=""):
    """下载音频 → ASR → 摘要
    video_tag: 用于区分不同视频的临时文件标识
    返回 (summary, audio_url_hash) 或 ("", "")
    """
    global _SEEN_AUDIO_URLS
    
    # 音频 URL 去重：同一段音频不重复处理
    url_hash = hashlib.md5(audio_url.encode()).hexdigest()[:12]
    if url_hash in _SEEN_AUDIO_URLS:
        print(f"    ⚠️ 音频 URL 重复，跳过")
        return "", ""
    _SEEN_AUDIO_URLS.add(url_hash)
    
    tag = video_tag or url_hash
    mp4 = os.path.join(TMP, f"_pw_{tag}.mp4")
    wav = os.path.join(TMP, f"_pw_{tag}.wav")
    
    # ffmpeg 下载
    subprocess.run([FFMPEG, "-y", "-i", audio_url, "-c", "copy", "-t", "180", mp4],
                   capture_output=True, timeout=60)
    if not os.path.exists(mp4) or os.path.getsize(mp4) < 1000:
        return "", ""
    
    # 转 WAV
    subprocess.run([FFMPEG, "-y", "-i", mp4, "-ac", "1", "-ar", "16000", "-t", "180", wav],
                   capture_output=True, timeout=30)
    
    if not os.path.exists(wav) or os.path.getsize(wav) < 1000:
        for f in [mp4, wav]:
            try: os.remove(f)
            except: pass
        return "", ""
    
    # Whisper
    model = get_whisper()
    r = model.transcribe(wav, language="zh", fp16=False, verbose=False)
    text = r["text"].strip()
    text = _clean_text(text)
    for f in [mp4, wav]:
        try: os.remove(f)
        except: pass
    
    # 质量检查：无明显内容的转录丢弃
    if len(text) < 10:
        return "", url_hash
    # 检查是否全是噪声（随机字符比例过高）
    alpha_ratio = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff') / max(len(text), 1)
    if alpha_ratio < 0.3:
        print(f"    ⚠️ 转录质量过低（中文占比 {alpha_ratio:.1%}），丢弃")
        return "", url_hash
    
    # 摘要
    events = re.split(r'(?=第[一二三四五六七八九十\d]+[件事个]|首先|另外|还有|接下来|最后|OK|下一件事)', text)
    if len(events) > 1:
        return "\n".join(f"  · {e.strip()[:80]}" for e in events[:6] if len(e.strip()) > 10), url_hash
    return text[:500], url_hash

def _scrape_page_desc(url):
    """Playwright 打开页面，抓取视频描述文本（ASR 失败时的降级方案）"""
    _kill_playwright()
    try:
        r = subprocess.run(
            ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} open \"{url}\""],
            capture_output=True, timeout=30, text=True, encoding="utf-8", errors="replace"
        )
        time.sleep(5)
        
        # 抓取页面可见文本，排除导航/按钮/页脚等噪音
        js = """
        (function(){
            var t = document.body.innerText;
            // 清理：去掉短行、链接、按钮文字、许可证信息
            var lines = t.split('\\n').filter(function(l){
                l = l.trim();
                if (l.length < 8) return false;
                if (/^(登录|注册|下载|打开|看更多|收藏|分享|评论|点赞|关注|粉丝|获赞|首页|推荐|朋友|我|合集|第\\d+集|ICP|许可证|京公网|网络文化|广播电视|增值电信)/.test(l)) return false;
                if (/^\\d+$/.test(l)) return false;
                if (/ICP备|公网安备|经营许可证|网络文化|互联网宗教|药品医疗|互联网新闻|违法和不良|算法推荐|网络内容从业人员|体育饭圈/.test(l)) return false;
                return true;
            });
            // 取前15行有实质内容的，排除视频标题（通常第一行就是标题）
            var desc = lines.slice(1, 15).join('\\n');
            return desc.substring(0, 1000);
        })()
        """
        r = subprocess.run(
            ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} eval \"{js}\""],
            capture_output=True, timeout=15, text=True, encoding="utf-8", errors="replace"
        )
        
        # 提取引号内的结果
        for line in r.stdout.split('\n'):
            line = line.strip()
            if line.startswith('"') and line.endswith('"'):
                text = line[1:-1].replace('\\n', '\n')
                if len(text) > 30:
                    _kill_playwright()
                    return _clean_text(text[:800])
        
        _kill_playwright()
        return None
    except Exception:
        _kill_playwright()
        return None


def main():
    global _SEEN_AUDIO_URLS
    _SEEN_AUDIO_URLS = set()  # 每次运行重置
    
    _kill_playwright()
    
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    # 只处理缺少 content_intro 或文案被污染的（备案信息/过短/非中文）
    all_bloggers = [a for a in d["articles"] if a.get("source") == "blogger" and "douyin.com" in (a.get("url") or "")]
    
    def _is_polluted(ci):
        """检测文案是否被备案信息/垃圾内容污染"""
        if not ci or len(ci) < 50:
            return True
        # 整行备案信息匹配
        garbage_lines = 0
        for line in ci.split('\n'):
            line = line.strip()
            if not line:
                continue
            if re.search(r'互联网宗教|药品医疗|互联网新闻|网上有害|不良信息举报|算法推荐.*?举报|网络内容.*?举报|体育饭圈|ICP备|公网安备|经营许可证|网络文化|广播电视|增值电信', line):
                garbage_lines += 1
        total_lines = max(len([l for l in ci.split('\n') if l.strip()]), 1)
        if garbage_lines >= 3 or garbage_lines / total_lines > 0.25:
            return True
        return False
    
    bloggers = [a for a in all_bloggers if _is_polluted(a.get("content_intro", ""))]
    
    print(f"\n🎉 免费 ASR: {len(bloggers)}/{len(all_bloggers)} 条待处理视频\n")
    
    if not bloggers:
        print("所有视频已有文案，无需 ASR")
        return
    
    # 收集已有的 content_intro 用于简单去重（仅检查完全相同）
    existing_intros = set()
    for v in all_bloggers:
        ci = v.get("content_intro", "")
        if ci and len(ci) > 50:
            existing_intros.add(ci[:100])  # 只比较前100字符
    
    def _save():
        """原子保存: 每次成功就写入"""
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    
    updated = 0
    failed_no_audio = 0
    for i, v in enumerate(bloggers):
        url = v.get("url", "")
        name = v.get("blogger_name", "")
        title = v.get("title", "")[:30]
        aweme_id = v.get("aweme_id", "")
        
        print(f"[{i+1}/{len(bloggers)}] {name} | {title}")
        
        try:
            audio_url = get_audio_url(url, expected_aweme_id=aweme_id)
            if not audio_url:
                print(f"  ⚠️ 未截获音频，尝试页面描述降级...")
                # 降级：直接从页面抓取视频描述文本
                desc = _scrape_page_desc(url)
                if desc and len(desc) > 30:
                    v["content_intro"] = desc
                    updated += 1
                    _save()
                    print(f"  ✅ 页面描述 {len(desc)}字 (已保存)")
                else:
                    print(f"  ⚠️ 页面描述无有效内容")
                    failed_no_audio += 1
                continue
            
            summary, url_hash = download_asr(audio_url, video_tag=aweme_id or str(i))
            if not summary:
                print(f"  ⚠️ ASR 失败或无有效内容")
                continue
            
            # 简单去重：完全相同的摘要跳过
            if summary[:100] in existing_intros:
                print(f"  ⚠️ 内容与已有视频完全相同，跳过")
                continue
            
            v["content_intro"] = summary
            existing_intros.add(summary[:100])
            updated += 1
            _save()  # 逐条保存
            print(f"  ✅ {len(summary)}字 (已保存)")
        except Exception as e:
            print(f"  ❌ {e}")
        print()
    
    _kill_playwright()
    
    # 最终重新生成 data.js
    if updated or failed_no_audio > 0:
        r = subprocess.run([sys.executable, "gen_js_data.py"], cwd=WORK, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ⚠️ gen_js_data 失败: {r.stderr[:200]}")
    
    print(f"\n✅ ASR 完成: 成功 {updated}/{len(bloggers)}，未截获音频 {failed_no_audio}")

if __name__ == "__main__":
    main()
