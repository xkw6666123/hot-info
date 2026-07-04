# -*- coding: utf-8 -*-
"""
Use system Chrome via Playwright (channel='chrome') to scrape Douyin
This avoids downloading a separate Chromium
"""
import asyncio, json, os, sys, re, time
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed")
    sys.exit(1)

BLOGGERS = [
    ("网吧信息差", "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"),
    ("阿七大型纪录片", "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf"),
    ("陈先生", "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF"),
    ("人类观察菌", "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN"),
]

async def scrape_blogger(page, name, sec_uid):
    url = "https://www.douyin.com/user/{}".format(sec_uid)
    print("  Opening: {}".format(url))
    
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(10000)
        
        title = await page.title()
        if "验证" in title or "verify" in title.lower():
            print("  CAPTCHA: {}".format(title))
            return []
        
        # Scroll to load videos
        for _ in range(4):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1500)
        
        # Extract video data
        videos = await page.evaluate('''() => {
            var results = [], seen = new Set();
            
            // Look for all video links on the user page
            document.querySelectorAll('a[href*="/video/"]').forEach(function(a) {
                var m = a.href.match(/video\\/(\\d+)/);
                if (!m || seen.has(m[1])) return;
                seen.add(m[1]);
                
                var text = (a.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 200);
                if (text.length < 3) return;
                
                // Find stats from nearby elements  
                var container = a.closest('[class*="item"]') || a.parentElement?.parentElement;
                var likesStr = "", commentStr = "";
                if (container) {
                    var allSpans = container.querySelectorAll('span, [class]');
                    for (var s of allSpans) {
                        var t = s.textContent.trim();
                        if (/\\d/.test(t)) {
                            if (!likesStr) likesStr = t;
                            else if (!commentStr && t !== likesStr) commentStr = t;
                        }
                    }
                }
                
                results.push({
                    id: m[1],
                    title: text,
                    likesText: likesStr,
                    commentText: commentStr
                });
            });
            
            return results.slice(0, 15);
        }''')
        
        results = []
        for v in videos[:5]:
            vid_id = v.get('id', '')
            title_text = v.get('title', '').strip()
            if not title_text or not vid_id:
                continue
            
            # Parse likes
            likes = 0
            lt = v.get('likesText', '')
            if lt:
                m2 = re.match(r'([\d.]+)万?', lt)
                if m2:
                    n = float(m2.group(1))
                    likes = int(n * 10000) if '万' in lt else int(n)
            
            results.append({
                'aweme_id': vid_id,
                'desc': title_text[:200],
                'likes': likes,
            })
            print("  [{}] id={} likes={} {}...".format(
                len(results), vid_id, likes, title_text[:35]))
        
        return results
        
    except Exception as e:
        print("  ERROR: {}".format(e))
        import traceback
        traceback.print_exc()
        return []

async def main():
    all_results = {}
    
    async with async_playwright() as p:
        # Use system Chrome with existing login session
        print("Launching Chrome (system browser)...")
        try:
            browser = await p.chromium.launch(
                channel='chrome',
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
        except Exception as e:
            print("Cannot launch Chrome: {}".format(e))
            print("Trying chromium...")
            browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        
        # Anti-detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        page = await context.new_page()
        
        # Visit douyin.com first
        print("\\nVisiting douyin.com...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            print("  Warning: {}".format(e))
        
        for name, sec_uid in BLOGGERS:
            print("\\n=== {} ===".format(name))
            videos = await scrape_blogger(page, name, sec_uid)
            all_results[name] = videos
            await page.wait_for_timeout(2000)
        
        await browser.close()
    
    print("\\n" + "=" * 50)
    print(json.dumps(all_results, ensure_ascii=False, indent=2))

async def scrape_browser(page, name, sec_uid):
    """Wrapper to avoid naming conflict"""
    return await scrape_blogger(page, name, sec_uid)

if __name__ == '__main__':
    asyncio.run(main())
