#!/usr/bin/env python3
"""ASR：Playwright 拦截音频 → ffmpeg下载 → 小米 MiMo ASR API → 摘要"""
import json, os, subprocess, time, re, sys, shutil, hashlib
import base64, urllib.request, urllib.error

# 繁简转换
try:
    from opencc import OpenCC
    _CC = OpenCC('t2s')  # 繁体→简体
except Exception:
    _CC = None

# 小米 MiMo ASR 配置
MIMO_API_KEY = os.environ.get('MIMO_API_KEY', 'tp-ct56cpxdmbbfsvma531fntsj2ru0a3584nz44oh3hxzodh6z')
MIMO_BASE_URL = 'https://token-plan-cn.xiaomimimo.com/v1'

D_TEMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'asr_temp')
os.makedirs(D_TEMP, exist_ok=True)
TMP = D_TEMP
WORK = os.path.dirname(os.path.abspath(__file__))
FFMPEG = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe") or "ffmpeg"
PCLI = "playwright-cli"

def mimo_asr(audio_path, language='zh'):
    """调用小米 MiMo ASR API 识别音频，返回文本"""
    # 读取音频并 base64 编码
    with open(audio_path, 'rb') as f:
        audio_bytes = f.read()
    
    if len(audio_bytes) < 1000:
        return ''
    
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
    
    # 判断 MIME 类型
    if audio_path.endswith('.mp3'):
        mime = 'audio/mpeg'
    elif audio_path.endswith('.wav'):
        mime = 'audio/wav'
    else:
        mime = 'audio/mpeg'
    
    payload = json.dumps({
        'model': 'mimo-v2.5-asr',
        'messages': [{
            'role': 'user',
            'content': [{
                'type': 'input_audio',
                'input_audio': {
                    'data': f'data:{mime};base64,{audio_b64}'
                }
            }]
        }],
        'asr_options': {'language': language},
        'max_tokens': 500
    }).encode('utf-8')
    
    headers = {
        'Authorization': f'Bearer {MIMO_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f'{MIMO_BASE_URL}/chat/completions',
                data=payload, headers=headers, method='POST'
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            
            text = ''
            if result.get('choices') and result['choices'][0].get('message'):
                text = result['choices'][0]['message'].get('content', '')
            return text.strip()
        except Exception as e:
            if attempt < 2:
                print(f'    MiMo ASR 重试 {attempt+2}/3: {e}')
                time.sleep(3)
            else:
                print(f'    MiMo ASR 失败: {e}')
                return ''

def _kill_playwright():
    """完全关闭 Playwright 浏览器 + 强制杀 Chrome/Node 进程"""
    # 1. playwright-cli 正常关闭
    subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} kill-all"],
                   capture_output=True, timeout=10)
    time.sleep(2)
    # 2. 强制杀残留 Chrome/Node（确保干净状态）
    try:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True, timeout=5)
    except Exception:
        pass
    try:
        subprocess.run(["taskkill", "/F", "/IM", "node.exe"], capture_output=True, timeout=5)
    except Exception:
        pass
    time.sleep(2)

# 连续 Playwright 失败计数器（超过阈值则跳过后续视频，只用降级方案）
_PW_FAIL_COUNT = 0
_PW_FAIL_MAX = 3

# ═══ 文本清洗 ═══
# Whisper 常见误识别 → 正确词（长匹配优先，避免短词先替换破坏长匹配）
_WHISPER_FIXES = [
    # ═══ 高频口语/语气词修正 ═══
    ('巴查', '八成'), ('巴扎', '八成'), ('巴拉', '八成'),
    ('这到吧', '这把'),
    ('那首线第一', '那首先第一'), ('加手先定着', '加上先定着'),
    
    # ═══ 专有名词 ═══
    ('山母', '山姆'), ('山姆超市', '山姆超市'),
    ('瑞幸在这段', '瑞幸在这段'),
    ('Hello Kitty', 'Hello Kitty'),
    ('H11Hello Kitty', 'Hello Kitty'),
    ('KT嘛', 'Kitty嘛'),
    ('何地着', '黑皮的'),
    
    # ═══ 常见错误词修正 ═══
    ('借王学校', '戒网学校'), ('戒网', '戒网'),
    ('多心肠保全', '多新鲜保全'),
    ('门位式', '门卫室'), ('减肥品', '捡废品'),
    ('龙餐', '弄散'), ('减肥品', '捡废品'),
    ('减废品', '捡废品'),
    ('玉章书院', '豫章书院'),
    ('新宿大二代', '新四大发明'),
    ('离他', '吉他'), ('厘他', '吉他'),
    ('一觉', '一脚'), 
    ('晴便', '倾翻'),
    ('自压裂嘴', '龇牙咧嘴'),
    ('眼我服了', '演技服了'),
    ('拔起了卖', '把起了脉'),
    ('死服伤', '救死扶伤'), ('救死负伤', '救死扶伤'),
    ('晴负伤', '救死扶伤'),
    
    # ═══ 常见动作/动词修正 ═══
    ('全讲', '拳脚'), ('全脚', '拳脚'),
    ('把刑法当日武兰州', '把刑法当日舞兰州'),
    ('摔车', '摔车'), ('害我摔车', '害我摔车'),
    ('撑死', '撑死'), ('我单手就能拎起来', '我单手就能拎起来'),
    ('蛇行定徽', '苏醒后'),
    ('阴阴静妹', '隐隐姐妹'),
    ('蓝头尸', '两头狮'), ('缝合', '缝合'),
    ('原币', '原地退役'), ('原币了', '原地退役了'),
    ('顶攻查', '顶公茬'),
    ('反守', '反手'), ('反守掏出', '反手掏出'),
    ('放狠狠', '放狠话'),
    ('前美感额', '钱没敢讹'),
    ('压著线', '压着线'),
    ('好屈服', '好欺负'),
    ('顺暴', '瞬爆'),
    ('云落', '陨落'),
    ('堕礁鱼头', '大脚鱼头'),
    ('照视者', '肇事者'),
    ('寡蹭', '剐蹭'),
    ('权责', '全责'),
    ('竞事', '沉浸'),
    ('三角钟', '三角洲'),
    ('成竞事', '沉浸式'),
    ('网管小姐', '网管小姐姐'),
    ('教怪', '叫怪'),
    ('硬是给骗', '硬是被骗'),
    ('出对象', '处对象'),
    ('品学兼优', '品学兼优'),
    ('千钢筋', '牵钢筋'),
    ('月老给你俩千钢筋', '月老给你俩牵钢筋'),
    
    # ═══ 常见名词修正 ═══
    ('基督犬', '缉毒犬'), ('基督', '缉毒'),
    ('海军将领', '海军将领'), ('海军', '海军'),
    ('训犬员', '训犬员'), ('训犬', '训犬'),
    ('警犬', '警犬'), ('狗子', '狗子'),
    ('罪名的', '最灵敏的'),
    ('死嘴', '死嘴'),
    ('人情事故', '人情世故'),
    ('贪心病', '贪心病'),
    ('新一件', '新一件'),
    ('美国护照', '美国护照'),
    ('大使馆', '大使馆'),
    ('翻译器', '翻译器'),
    ('加塞', '加塞'),
    ('网约车', '网约车'),
    ('电动车', '电动车'), ('反电动车', '反电动车'),
    ('头盔', '头盔'), ('带头盔', '戴头盔'),
    ('快递车', '快递车'), ('货车', '货车'),
    ('信信号灯', '信号灯'), ('红灯', '红灯'), ('绿灯', '绿灯'),
    ('泥潭', '泥潭'), ('油门', '油门'),
    ('后车', '后车'), ('前车', '前车'),
    ('奥迪', '奥迪'), ('绿车', '绿车'),
    ('大货车', '大货车'), ('路口', '路口'),
    ('电动车', '电动车'), ('镜子', '镜子'), ('臭美', '臭美'),
    ('白车', '白车'), ('路障', '路障'), ('路灯', '路灯'),
    ('施工师傅', '施工师傅'), ('外卖小哥', '外卖小哥'),
    ('倒霉熊', '倒霉熊'), ('续集', '续集'),
    ('沙发', '沙发'), ('手机', '手机'),
    
    # ═══ 气候/天气 ═══
    ('强队', '强对流'), ('强队的天气', '强对流的天气'),
    ('风果', '风裹'), ('云层', '云层'), ('沙尘', '沙尘'),
    ('过山车', '过山车'), ('演唱会', '演唱会'),
    ('棚顶', '棚顶'), ('停业', '停业'),
    
    # ═══ 人物/身份 ═══
    ('小公然', '小姑娘'), ('品学兼优', '品学兼优'),
    ('中医事家', '中医世家'), ('实名', '石铭'),
    ('甜妹', '甜妹'), ('软软糯糯', '软软糯糯'),
    ('高扫腿', '高扫腿'), ('解收员', '解说员'),
    ('木乃伊', '木乃伊'),
    ('印度一节托马尔', '印度一姐托马尔'),
    ('患者不是等来的', '患者不是等来的'),
    
    # ═══ 高频错误词对 ═══
    ('公然的', '姑娘的'), ('公然', '姑娘'),
    ('博主的', '博主的'), ('车牌', '车牌'), ('驾照', '驾照'),
    ('贴膜', '贴膜'), ('自驾', '自驾'),
    ('停车场', '停车场'), ('考驾照', '考驾照'),
    ('风土人情', '风土人情'),
    ('走人', '走人'), ('被斩一刀', '被宰一刀'),
    ('先领后兵', '先礼后兵'),
    ('一秒天黑', '一秒天黑'),
    ('擦边冒牌', '擦边冒牌'),
    ('归根结底', '归根结底'),
    ('试验过的', '试验过的'),
    ('诗言社', '实验室'),
    ('丑话', '丑化'), ('丑话人家', '丑化人家'),
    ('高视整面', '好事正面'),
    ('感情牌', '感情牌'), ('攻列', '攻略'),
    
    # ═══ 常见品牌/平台 ═══
    ('Mimi发家', '小米发家'), ('Mimi', '小米'),
    ('优用', '优惠券'),
    ('七四九', '749'), ('749局', '749局'),
    
    # ═══ 哈尔滨相关 ═══
    ('哈尔滨', '哈尔滨'), ('13级', '13级'), ('14级', '14级'),
    
    # ═══ 集合词修复 ═══
    ('UFC', 'UFC'), ('OK', 'OK'), ('KO', 'KO'),
    ('oooh my gosh', 'oh my gosh'),
    
    # ═══ 日语句修正 ═══
    ('你爆一个四十', '你爆一个试试'),
    ('浓的要小', '弄的要死'),
    ('豆豆里头', '豆豆里'),
    
    # 著→着 常见模式
    ('想著', '想着'), ('握著', '握着'), ('看著', '看着'),
    ('听著', '听着'), ('拿著', '拿着'), ('跟著', '跟着'),
    ('带著', '带着'), ('提著', '提着'), ('对著', '对着'),
    ('抱著', '抱着'), ('坐著', '坐着'), ('站著', '站着'),
    ('走著', '走着'), ('笑著', '笑着'), ('吃著', '吃着'),
    ('喝著', '喝着'), ('写著', '写着'), ('说著', '说着'),
    ('唱著', '唱着'), ('跑著', '跑着'), ('拉著', '拉着'),
    ('推著', '推着'), ('装著', '装着'), ('藏著', '藏着'),
    ('放著', '放着'), ('留著', '留着'),
    
    # 杂项
    ('三娘我请我来哦', ''),
]

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
    
    # Whisper 常见误识别修复（按顺序，长匹配在前）
    for wrong, right in _WHISPER_FIXES:
        text = text.replace(wrong, right)
    
    lines = [l.strip() for l in text.split(chr(10))]
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
    global _PW_FAIL_COUNT
    
    # 连续失败太多，直接跳过
    if _PW_FAIL_COUNT >= _PW_FAIL_MAX:
        print(f"    ⚠️ Playwright 连续失败{_PW_FAIL_COUNT}次，跳过")
        return None
    
    _kill_playwright()
    
    # 打开页面，用 longer wait + retry if page fails to load
    success = False
    for attempt in range(2):  # 减少重试次数从3到2
        try:
            r = subprocess.run(
                ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} open \"{video_url}\""],
                capture_output=True, timeout=25, text=True, encoding="utf-8", errors="replace"
            )
            success = True
            break
        except subprocess.TimeoutExpired:
            if attempt < 1:
                _kill_playwright()
                time.sleep(3)
    
    if not success:
        _PW_FAIL_COUNT += 1
        print(f"    ⚠️ Playwright open 超时 (失败{_PW_FAIL_COUNT}/{_PW_FAIL_MAX})")
        _kill_playwright()
        return None
    
    _PW_FAIL_COUNT = 0  # 成功则重置计数器
    time.sleep(8)  # 抖音需要时间触发视频加载
    
    # 尝试点击页面触发视频播放（抖音延迟加载）
    try:
        subprocess.run(["bash", "-c", f"unset NODE_OPTIONS && {PCLI} click e1"],
                       capture_output=True, timeout=5, text=True)
        time.sleep(5)  # 额外等待播放触发后的请求
    except Exception:
        pass
    
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
    
    # 如果没找到分离音频，找 video URL（新版抖音合并流或旧版 mp4）
    # 新版抖音 douyinvod.com URL 可能同时含音视频
    video_urls = []
    for line in requests_output.split("\n"):
        if ("media-video-avc1" in line and "douyinvod.com" in line) or \
           ("douyinvod.com" in line and ("/video/" in line or br_match(line))):
            parts = line.split("=>")
            for part in parts:
                if "douyinvod.com" in part:
                    url_raw = part.strip().split(" ")[-1].strip("[]")
                    url = urllib.parse.unquote(url_raw)
                    # 去重，优先匹配 aweme_id
                    if url not in [u for u, _ in video_urls]:
                        priority = 1 if (expected_aweme_id and expected_aweme_id in url) else 0
                        video_urls.append((url, priority))
    
    # 优先返回匹配 aweme_id 的 URL
    for u, p in sorted(video_urls, key=lambda x: -x[1]):
        if u and "douyinvod.com" in u:
            _kill_playwright()
            return u
    
    _kill_playwright()
    return None

def br_match(line):
    """检查行中是否有 douyinvod.com URL（新版格式）"""
    import re as _re
    return bool(_re.search(r'douyinvod\.com/[^?\s]+\?[^?\s]*br=\d+', line))

# 全局去重：记录已处理的音频 URL，防止跨视频复用
_SEEN_AUDIO_URLS = set()

def download_asr(audio_url, video_tag="", max_sec=120):
    """下载音频 → MiMo ASR → 完整原文案
    video_tag: 用于区分不同视频的临时文件标识
    max_sec: 最大音频时长（秒），短视频120s足够
    返回 (transcript, audio_url_hash) 或 ("", "")
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
    mp3 = os.path.join(TMP, f"_pw_{tag}.mp3")
    
    # ffmpeg 下载（抖音合并流需要 Referer header）
    ffmpeg_cmd = [FFMPEG, "-y", "-i", audio_url, "-c", "copy", "-t", str(max_sec), mp4]
    if "douyinvod.com" in audio_url or "douyin.com" in audio_url:
        ffmpeg_cmd = [FFMPEG, "-y", "-headers", "Referer: https://www.douyin.com/\r\n", 
                      "-i", audio_url, "-c", "copy", "-t", str(max_sec), mp4]
    subprocess.run(ffmpeg_cmd, capture_output=True, timeout=60)
    if not os.path.exists(mp4) or os.path.getsize(mp4) < 1000:
        return "", ""
    
    # 转 MP3（MiMo API 支持 mp3/wav，mp3 体积更小）
    subprocess.run([FFMPEG, "-y", "-i", mp4, "-ac", "1", "-ar", "16000", "-b:a", "32k", "-t", str(max_sec), mp3],
                   capture_output=True, timeout=30)
    
    if not os.path.exists(mp3) or os.path.getsize(mp3) < 1000:
        for f in [mp4, mp3]:
            try: os.remove(f)
            except: pass
        return "", ""
    
    # 小米 MiMo ASR
    text = mimo_asr(mp3, language='zh')
    text = _clean_text(text)
    for f in [mp4, mp3]:
        try: os.remove(f)
        except: pass
    
    # 质量检查：无明显内容的转录丢弃
    if len(text) < 10:
        return "", url_hash
    # 检查是否全是噪声（中文字符比例过低）
    alpha_ratio = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff') / max(len(text), 1)
    if alpha_ratio < 0.3:
        print(f"    ⚠️ 转录质量过低（中文占比 {alpha_ratio:.1%}），丢弃")
        return "", url_hash
    
    # 返回完整 cleaned 文案（最多2000字）
    return text[:2000], url_hash

def _scrape_page_desc(url):
    """Playwright 打开页面，抓取视频描述文本（ASR 失败时的降级方案）"""
    global _PW_FAIL_COUNT
    if _PW_FAIL_COUNT >= _PW_FAIL_MAX:
        return None
    
    _kill_playwright()
    try:
        r = subprocess.run(
            ["bash", "-c", f"unset NODE_OPTIONS && {PCLI} open \"{url}\""],
            capture_output=True, timeout=25, text=True, encoding="utf-8", errors="replace"
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
        for line in r.stdout.split(chr(10)):
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


def _fetch_url(url, headers=None, timeout=15):
    """HTTP GET (本地版本，用于B站API等)"""
    import urllib.request, urllib.error, gzip as _gzip
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/json,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        default_headers.update(headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        req = urllib.request.Request(url, headers=default_headers)
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            encoding = resp.headers.get("Content-Encoding", "")
            if "gzip" in encoding:
                raw = _gzip.decompress(raw)
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    ⚠️ fetch失败: {e}")
        return None

def _bilibili_asr(url):
    """B站视频ASR：遍历所有音频流，下载后用 MiMo API 识别"""
    bv_match = re.search(r'BV[\w]+', url)
    if not bv_match:
        return None
    bvid = bv_match.group(0)
    try:
        info = json.loads(_fetch_url("https://api.bilibili.com/x/web-interface/view?bvid=" + bvid))
        if info.get("code") != 0:
            return None
        data = info.get("data", {})
        cid = data.get("cid", 0)
        if not cid:
            return None
        play = json.loads(_fetch_url("https://api.bilibili.com/x/player/playurl?bvid=" + bvid + "&cid=" + str(cid) + "&qn=16&fnval=16"))
        if play.get("code") != 0:
            return None
        audios = play.get("data", {}).get("dash", {}).get("audio", [])
        if not audios:
            return None
        # Try all audio streams
        audio_path = None
        for a_entry in audios:
            au = a_entry.get("baseUrl") or a_entry.get("base_url", "")
            bu = a_entry.get("backupUrl") or a_entry.get("backup_url", [])
            if isinstance(bu, str):
                bu = [bu]
            for u in [au] + (bu if bu else []):
                if not u:
                    continue
                import tempfile
                path = os.path.join(tempfile.gettempdir(), "bili_" + bvid + ".mp3")
                subprocess.run(
                    ["ffmpeg", "-y", "-i", u, "-headers", "Referer: https://www.bilibili.com/" + chr(13) + chr(10),
                     "-ac", "1", "-ar", "16000", "-b:a", "32k", "-t", "180", path],
                    capture_output=True, timeout=60)
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    audio_path = path
                    break
                elif os.path.exists(path):
                    try: os.remove(path)
                    except: pass
            if audio_path:
                break
        if not audio_path:
            return None
        text = mimo_asr(audio_path, language='zh')
        try: os.remove(audio_path)
        except: pass
        if len(text) < 10:
            return None
        return _clean_text(text[:2000])
    except Exception as e:
        print("    B站ASR: " + str(e))
        return None

def get_bilibili_content(url):
    """B站视频内容提取：API获取描述和字幕"""
    bv_match = re.search(r'BV[\w]+', url)
    if not bv_match:
        return None
    bvid = bv_match.group(0)
    
    # 方法0：ASR音频识别（最可靠）
    asr_text = _bilibili_asr(url)
    if asr_text and len(asr_text) > 30:
        return asr_text
    
    # B站 API 获取视频信息
    try:
        info_url = "https://api.bilibili.com/x/web-interface/view?bvid=" + bvid
        info_text = _fetch_url(info_url)
        if not info_text:
            return None
        info = json.loads(info_text)
        if info.get("code") != 0:
            return None
        data = info.get("data", {})
        desc = data.get("desc", "")
        cid = data.get("cid", 0)
        
        # 尝试获取字幕
        if cid:
            sub_url = "https://api.bilibili.com/x/player/v2?bvid=" + bvid + "&cid=" + str(cid)
            sub_text = _fetch_url(sub_url)
            if sub_text:
                sub_data = json.loads(sub_text)
                if sub_data.get("code") == 0:
                    subtitles = sub_data.get("data", {}).get("subtitle", {}).get("subtitles", [])
                    if subtitles:
                        sub_url_path = subtitles[0].get("subtitle_url", "")
                        if sub_url_path:
                            if sub_url_path.startswith("//"):
                                sub_url_path = "https:" + sub_url_path
                            sub_content = _fetch_url(sub_url_path)
                            if sub_content:
                                sub_json = json.loads(sub_content)
                                body = sub_json.get("body", [])
                                parts = [item.get("content", "") for item in body if item.get("content")]
                                if parts:
                                    return _clean_text(chr(10).join(parts[:50])[:2000])
        
        # 没有字幕，用描述
        if desc and len(desc) > 20:
            return _clean_text(desc[:500])
        
        # 都没有，用标题+标签
        title = data.get("title", "")
        tags = [t.get("tag_name","") for t in data.get("tag", {}).get("tag_list", []) if t.get("tag_name")]
        if title:
            result = title
            if tags:
                result += "。标签：" + "、".join(tags[:5])
            return _clean_text(result[:300])
    except Exception as e:
        print("    B站API: " + str(e))
    
    # 方法2：Playwright 抓取页面内容
    try:
        _kill_playwright()
        subprocess.run(
            ["bash", "-c", "unset NODE_OPTIONS && " + PCLI + " open \"" + url + "\"" ],
            capture_output=True, timeout=30, text=True, encoding="utf-8", errors="replace"
        )
        time.sleep(6)
        js_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bili_eval.js")
        r = subprocess.run(
            ["bash", "-c", "unset NODE_OPTIONS && " + PCLI + " eval \"\$(cat \"" + js_file + "\"" ],
            capture_output=True, timeout=15, text=True, encoding="utf-8", errors="replace"
        )
        for line in r.stdout.split(chr(10)):
            line = line.strip()
            if line.startswith('"') and line.endswith('"'):
                text = line[1:-1]
                if len(text) > 30:
                    _kill_playwright()
                    return _clean_text(text[:2000])
        _kill_playwright()
    except Exception as e:
        print("    B站PW: " + str(e))
        _kill_playwright()
    
    return None

def main():
    global _SEEN_AUDIO_URLS, _PW_FAIL_COUNT
    _SEEN_AUDIO_URLS = set()  # 每次运行重置
    _PW_FAIL_COUNT = 0        # 重置失败计数器
    
    _kill_playwright()
    
    with open("data.json", "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    
    # 需要重新提取的视频：ASR失败/过短/AI摘要/页面噪声
    all_bloggers = [a for a in d["articles"] if a.get("source") == "blogger" and ("douyin.com" in (a.get("url") or "") or "bilibili.com" in (a.get("url") or ""))]
    
    def _needs_re_extract(ci):
        """判断文案是否需要重新提取（非1:1原文案）"""
        if not ci or len(ci) < 100:
            return True  # 过短→空壳
        # AI摘要特征：章节要点/今日热点包括/热点事件包括
        if any(kw in ci[:50] for kw in ['章节要点', '今日热点包括', '热点事件包括', '5月', '6月']):
            return True
        # 抓取噪声特征：含商业推广/备案/无关内容
        noise_kw = ['网络谣言曝光台', '抖音神曲', '特斯拉', '#汽车知识', 'ICP备', '俄语', 
                     '日语教学', '灌录盘', '马拉松', '肺动脉高压', '华贸鞋业']
        noise_count = sum(1 for kw in noise_kw if kw in ci)
        if noise_count >= 2:
            return True
        # 仅标题+标签
        if ci.count('\n') <= 2 and ('话题：' in ci or '#' in ci):
            return True
        return False
    
    # 只处理需要重新提取的视频（空/过短/噪声）
    bloggers = [v for v in all_bloggers if _needs_re_extract(v.get("content_intro", ""))]
    
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
    skipped_pw = 0
    for i, v in enumerate(bloggers):
        url = v.get("url", "")
        name = v.get("blogger_name", "")
        title = v.get("title", "")[:30]
        aweme_id = v.get("aweme_id", "")
        ci = v.get("content_intro", "")
        
        # 如果已有高质量文案(>300字非噪声)，跳过
        if len(ci) > 300 and not _needs_re_extract(ci):
            print(f"[{i+1}/{len(bloggers)}] {name} | {title[:20]}... ⏭️ 已有{len(ci)}字文案")
            continue
        
        print(f"[{i+1}/{len(bloggers)}] {name} | {title}")
        
        try:
            # B站视频：用字幕API提取
            if "bilibili.com" in url:
                print(f"  📺 B站视频，提取字幕/描述...")
                bili_text = get_bilibili_content(url)
                if bili_text and len(bili_text) > 30:
                    v["content_intro"] = bili_text
                    existing_intros.add(bili_text[:100])
                    updated += 1
                    _save()
                    print(f"  ✅ B站内容 {len(bili_text)}字 (已保存)")
                else:
                    print(f"  ⚠️ B站内容提取失败或过短")
                    failed_no_audio += 1
                continue
            
            # 抖音视频：Playwright 连续失败太多，跳过
            if _PW_FAIL_COUNT >= _PW_FAIL_MAX:
                print(f"  ⚠️ Playwright已连续失败{_PW_FAIL_COUNT}次，跳过剩余抖音视频")
                skipped_pw += len(bloggers) - i
                break
            
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
    
    print(f"\n✅ ASR 完成: 成功 {updated}/{len(bloggers)}，未截获音频 {failed_no_audio}，Playwright跳过 {skipped_pw}")

if __name__ == "__main__":
    main()
