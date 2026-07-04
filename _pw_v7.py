# -*- coding: utf-8 -*-
"""
Playwright v7 - Network interception approach
Instead of scraping DOM (which shows recommended content for unauthenticated users),
intercept the actual API responses that Douyin's SPA fetches.
This gives us REAL blogger video data even without login.
"""
import asyncio, json, sys, re, os
from datetime import datetime, timezone, timedelta

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed")
    sys.exit(1)

CST = timezone(timedelta(hours=8))

BLOGGERS = [
    ("网吧信息差", "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"),
    ("阿七大型纪录片", "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf"),
    ("陈先生", "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF"),
    ("人类观察菌", "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN"),
]

# API URL patterns to intercept
API_PATTERNS = [
    '/aweme/v1/web/aweme/post/',      # User post videos API
    '/aweme/v1/web/aweme/feed/',      # Feed API (sometimes used)
    '/v1/web/aweme/post/',            # Alternate post endpoint
    '/api/user/list?',                # Another pattern
]


def parse_dy_date(date_str):
    if not date_str:
        return ""
    date_str = date_str.strip()
    now = datetime.now(CST)
    m = re.match(r'^(\d{2})-(\d{2})$', date_str)
    if m:
        return f"{now.year}-{m.group(1)}-{m.group(2)}"
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
    if m:
        return date_str
    m = re.match(r'^(\d+)天前$', date_str)
    if m:
        d = now - timedelta(days=int(m.group(1)))
        return d.strftime("%Y-%m-%d")
    m = re.match(r'^(\d+)小时前$', date_str)
    if m:
        d = now - timedelta(hours=int(m.group(1)))
        return d.strftime("%Y-%m-%d")
    if "刚刚" in date_str or "分钟前" in date_str:
        return now.strftime("%Y-%m-%d")
    return date_str


async def scrape_blogger_with_network(page, name, sec_uid):
    """Scrape blogger by intercepting network API responses"""
    url = f"https://www.douyin.com/user/{sec_uid}"
    print(f"\n{'='*55}")
    print(f"=== {name} ===")
    
    api_responses = []
    
    # Set up response interception BEFORE navigation
    async def handle_response(response):
        resp_url = response.url
        # Check if this is an aweme/video API call
        for pattern in API_PATTERNS:
            if pattern in resp_url:
                try:
                    body = await response.text()
                    if body and len(body) > 50:
                        api_responses.append({
                            'url': resp_url,
                            'status': response.status,
                            'body': body,
                        })
                        print(f"  [API] Captured: {pattern} ({len(body)} bytes, status={response.status})")
                except Exception as e:
                    print(f"  [API] Error reading {pattern}: {e}")
                break
    
    page.on('response', handle_response)
    
    try:
        print(f"  Opening with network intercept...")
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        
        # Wait for initial load + API calls
        await page.wait_for_timeout(10000)
        
        # Click "作品" tab to trigger the actual data API call
        clicked = await page.evaluate("""() => {
            var tabs = document.querySelectorAll('[class*="tab"], [role="tab"], [data-e2e*="tab"]');
            var best = null, bestP = 999;
            for (var t of tabs) {
                var txt = t.textContent.trim();
                var p;
                if (txt === '作品') p = 1;
                else if (txt === '视频') p = 2;
                else if (txt === '喜欢') p = 99;
                else continue;
                if (p < bestP) { bestP = p; best = t; }
            }
            if (best) { best.click(); return txt; }
            return null;
        }""")
        if clicked:
            print(f"  Clicked tab: [{clicked}]")
            # Wait for the API call triggered by tab click
            await page.wait_for_timeout(8000)
        
        # Scroll down to trigger lazy loading (more API calls)
        for i in range(5):
            await page.evaluate(f"window.scrollBy(0, 3000)")
            await page.wait_for_timeout(4000)
            
            current_count = len(api_responses)
            print(f"  Scroll #{i+1}: captured {current_count} API responses so far")
        
        # Remove listener
        page.remove_listener('response', handle_response)
        
        # Parse all captured API responses
        videos = []
        for resp in api_responses:
            try:
                body = resp['body']
                data = json.loads(body) if isinstance(body, str) else body
                
                # TikHub-style response wrapper
                aweme_list = []
                if isinstance(data, dict):
                    # Direct Douyin API response
                    if 'aweme_list' in data:
                        aweme_list = data['aweme_list']
                    elif 'data' in data and isinstance(data['data'], dict):
                        if 'aweme_list' in data['data']:
                            aweme_list = data['data']['aweme_list']
                    elif 'data' in data and isinstance(data['data'], list):
                        aweme_list = data['data']
                
                if aweme_list:
                    print(f"  [PARSE] Found {len(aweme_list)} videos in response!")
                    for item in aweme_list[:10]:
                        vid = str(item.get('aweme_id', ''))
                        if not vid or not vid.isdigit():
                            continue
                        desc = (item.get('desc', '') or '').strip()
                        stats = item.get('statistics', {}) or {}
                        create_time = item.get('create_time', 0)
                        
                        # Convert timestamp
                        if create_time and isinstance(create_time, (int, float)) and create_time > 1000000000:
                            dt = datetime.fromtimestamp(create_time, tz=CST)
                            date_parsed = dt.strftime("%Y-%m-%d")
                        else:
                            date_parsed = ""
                        
                        videos.append({
                            'aweme_id': vid,
                            'desc': desc[:200],
                            'title': desc[:200],
                            'likes': stats.get('digg_count', 0) or 0,
                            'comments': stats.get('comment_count', 0) or 0,
                            'shares': stats.get('share_count', 0) or 0,
                            'date': date_parsed,
                        })
            except Exception as e:
                print(f"  [PARSE] Error: {e}")
        
        # Deduplicate by aweme_id
        seen_ids = set()
        unique_videos = []
        for v in videos:
            if v['aweme_id'] not in seen_ids:
                seen_ids.add(v['aweme_id'])
                unique_videos.append(v)
        
        # Output results
        results = unique_videos[:10]
        print(f"\n  Total unique videos: {len(results)}")
        for i, v in enumerate(results):
            print(f"  [{i+1}] id={v['aweme_id']} date={v.get('date','')} "
                  f"likes={v['likes']} c={v['comments']} | {v['desc'][:60]}")
        
        return results
        
    except Exception as e:
        page.remove_listener('response', handle_response)
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []


async def main():
    all_results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel='msedge',
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        page = await context.new_page()

        # Warm up
        print("Warming up...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  Warmup warning: {e}")

        for name, sec_uid in BLOGGERS:
            videos = await scrape_blogger_with_network(page, name, sec_uid)
            all_results[name] = videos

        await browser.close()

    print("\n" + "=" * 60)
    total = sum(len(v) for v in all_results.values())
    print(f"TOTAL: {total} videos from {len(all_results)} bloggers")
    for name, vids in all_results.items():
        print(f"  {name}: {len(vids)} videos")
        if vids:
            latest = max((v.get('date', '') for v in vids), default='')
            print(f"    Latest date: {latest}")

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_scrape_v7_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {output_file}")


if __name__ == '__main__':
    asyncio.run(main())
