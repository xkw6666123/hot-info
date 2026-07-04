"""测试 TikHub API 是否能获取最新抖音博主视频"""
import os, json, urllib.request, urllib.error
from datetime import datetime

TIKHUB_API_KEY = os.environ.get("TIKHUB_API_KEY", "")
print("TIKHUB_API_KEY set:", bool(TIKHUB_API_KEY))
if TIKHUB_API_KEY:
    print("Key prefix:", TIKHUB_API_KEY[:10] + "...")
else:
    # 尝试从 .env 或其他位置加载
    for p in ['.env', '../.env']:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('TIKHUB_API_KEY='):
                        TIKHUB_API_KEY = line.split('=', 1)[1].strip('"').strip("'")
                        print(f"Loaded from {p}")
                        break

if not TIKHUB_API_KEY:
    print("ERROR: No TIKHUB_API_KEY available")
    exit(1)

BASE = "https://api.tikhub.io"

def tikhub_request(endpoint, params=None, method="GET"):
    url = f"{BASE}{endpoint}"
    data = json.dumps(params).encode() if params else None
    req = urllib.request.Request(url, data=data, method=method,
        headers={"Authorization": f"Bearer {TIKHUB_API_KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Request error: {e}")
        return None

# 测试每个博主
bloggers = [
    ("网吧信息差", "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"),
    ("阿七大型纪录片", "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf"),
    ("陈先生", "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF"),
    ("人类观察菌", "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN"),
]

for name, sec_uid in bloggers:
    print(f"\n=== {name} ===")
    result = tikhub_request("/api/v1/douyin/app/v3/fetch_user_post_videos",
        {"sec_user_id": sec_uid, "max_cursor": 0, "count": 5}, method="GET")
    if result and result.get("code") == 200:
        data = result.get("data", {})
        aweme_list = data.get("aweme_list") or []
        print(f"  Got {len(aweme_list)} videos")
        for v in aweme_list[:5]:
            desc = (v.get('desc') or '')[:40]
            ct = v.get('create_time', 0)
            aid = v.get('aweme_id', '')
            dt = datetime.fromtimestamp(ct).strftime('%Y-%m-%d %H:%M') if ct else '?'
            stats = v.get('statistics', {}) or {}
            digg = stats.get('digg_count', 0) or 0
            print(f"  id={aid} time={dt} desc={desc} likes={digg}")
    else:
        print(f"  FAILED: {result}")
