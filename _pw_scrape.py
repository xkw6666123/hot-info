# -*- coding: utf-8 -*-
"""
Playwright-based Douyin blogger scraper
Uses persistent browser context to access logged-in state
"""
import asyncio, json, os, sys, time
from datetime import datetime

# Try importing playwright
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BLOGGERS = [
    ("网吧信息差", "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"),
    ("阿七大型纪录片", "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf"),
    ("陈先生", "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF"),
    ("人类观察菌", "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN"),
]

async def scrape_blogger(page, name, sec_uid):
    """Scrape one blogger's latest videos"""
    url = "https://www.douyin.com/user/{}".format(sec_uid)
    print("  Opening {}...".format(url))
    
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        status = response.status if response else 0
        print("  Status: {}".format(status))
        
        # Wait for video list to load
        await page.wait_for_timeout(8000)
        
        # Check for captcha/verification page
        title = await page.title()
        if "验证" in title:
            print("  CAPTCHA DETECTED: {}".format(title))
            return []
        
        # Scroll down to load more videos
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(2000)
        
        # Extract video data from the page using JavaScript
        videos = await page.evaluate('''() => {
            var results = [];
            var seen = new Set();
            
            // Method 1: Look for video links in the user post list
            var containers = document.querySelectorAll('[data-e2e="user-post-list"] > div, [class*="videoList"] > div');
            
            // Fallback: look for all video links on the page
            var allLinks = document.querySelectorAll('a[href*="/video/"]');
            
            allLinks.forEach(function(a) {
                var match = a.href.match(/video\\/(\\d+)/);
                if (!match || seen.has(match[1])) return;
                seen.add(match[1]);
                
                var text = (a.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 200);
                if (text.length < 3) return;
                
                // Try to find stats nearby
                var container = a.closest('[class*="item"]') || a.parentElement;
                var likesText = "";
                if (container) {
                    var likeEl = container.querySelector('[class*="count"], [class*="like"], [class*="digg"]');
                    if (likeEl) likesText = likeEl.textContent.trim();
                }
                
                results.push({
                    id: match[1],
                    title: text,
                    url: a.href,
                    likesHint: likesText
                });
            });
            
            return results.slice(0, 10);
        }''')
        
        print("  Found {} raw video elements".format(len(videos)))
        
        # Parse likes and build result
        results = []
        for v in videos[:5]:
            vid_id = v.get('id', '')
            title = v.get('title', '').strip()
            likes = 0
            
            # Parse likes text like "28.7万" or "12345"
            likes_hint = v.get('likesHint', '')
            if likes_hint:
                import re
                m = re.match(r'([\d.]+)万?', likes_hint)
                if m:
                    n = float(m.group(1))
                    likes = int(n * 10000) if '万' in likes_hint else int(n)
            
            if title and vid_id:
                results.append({
                    'aweme_id': vid_id,
                    'desc': title[:200],
                    'likes': likes,
                })
                print("  [{}] id={} title={}... likes={}".format(
                    len(results), vid_id, title[:30], likes))
        
        return results
        
    except Exception as e:
        print("  ERROR scraping {}: {}".format(name, e))
        return []

async def main():
    all_results = {}
    
    async with async_playwright() as p:
        # Launch browser with persistent context to use Chrome's cookies
        # Use Chromium since we need to access douyin.com
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        
        page = await context.new_page()
        
        # First visit douyin.com to establish base cookies
        print("\\nVisiting douyin.com...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            print("  Warning: {}".format(e))
        
        # Scrape each blogger
        for name, sec_uid in BLOGGERS:
            print("\\n=== {} ===".format(name))
            videos = await scrape_blogger(page, name, sec_uid)
            all_results[name] = videos
            if videos:
                print("  Total: {} videos".format(len(videos)))
            
            # Delay between bloggers
            await page.wait_for_timeout(3000)
        
        await browser.close()
    
    # Output JSON
    print("\\n" + "=" * 50)
    print(json.dumps(all_results, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
