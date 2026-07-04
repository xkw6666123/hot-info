# -*- coding: utf-8 -*-
"""
Use system Chrome via Playwright to scrape Douyin - Enhanced v2
Better selectors, more debug info, longer wait times
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
        resp = await page.goto(url, wait_until="networkidle", timeout=45000)
        status = resp.status if resp else "?"
        print("  HTTP Status: {}".format(status))

        # Wait for page to fully render
        await page.wait_for_timeout(8000)

        title = await page.title()
        print("  Page title: {}".format(title[:80]))

        if "验证" in title or "verify" in title.lower() or "安全" in title:
            print("  CAPTCHA/SECURITY detected!")
            # Try to wait for captcha to auto-resolve
            await page.wait_for_timeout(5000)
            title2 = await page.title()
            print("  After wait title: {}".format(title2[:80]))

        # Debug: check page content
        body_len = await page.evaluate("() => document.body.innerText.length")
        html_len = await page.evaluate("() => document.body.innerHTML.length")
        link_count = await page.evaluate("() => document.querySelectorAll('a').length")
        video_link_count = await page.evaluate("() => document.querySelectorAll('a[href*=\"video\"]').length")
        print("  Body text: {} chars, HTML: {} chars, Links: {}, Video links: {}".format(
            body_len, html_len, link_count, video_link_count))

        # Check for specific Douyin video containers
        container_info = await page.evaluate('''() => {
            var selectors = [
                '[data-e2e="user-post-list"]',
                '[data-e2e="user-post-list"] li',
                '.video-item',
                '[class*="video-card"]',
                '[class*="item"]',
                '[id*="video"]',
                '[class*="list-item"]'
            ];
            var results = {};
            for (var s of selectors) {
                var count = document.querySelectorAll(s).length;
                if (count > 0) results[s] = count;
            }
            return results;
        }''')
        if container_info:
            print("  Containers found: {}".format(container_info))

        # Scroll multiple times to trigger lazy loading
        for i in range(6):
            scroll_result = await page.evaluate('''(i) => {
                window.scrollBy(0, 800);
                // Also try scrolling inner containers
                var containers = document.querySelectorAll('[class*="scroll"], [class*="container"], [class*="list"]');
                containers.forEach(function(c) { c.scrollTop += 300; });
                return window.scrollY;
            }''', i)
            await page.wait_for_timeout(2000)
            after_links = await page.evaluate("() => document.querySelectorAll('a[href*=\"video\"]').length")
            print("  Scroll {}: scrollY={}, video_links={}".format(i+1, scroll_result, after_links))

        # Final video link count
        final_video_links = await page.evaluate("() => document.querySelectorAll('a[href*=\"video\"]').length")
        print("  Total video links after scroll: {}".format(final_video_links))

        # Extract video data - try multiple strategies
        videos = await page.extract_all_videos()

        results = []
        for v in videos[:5]:
            vid_id = v.get('id', '')
            title_text = v.get('title', '').strip()
            if not title_text or not vid_id:
                continue

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
                len(results), vid_id, likes, title_text[:40]))

        return results

    except Exception as e:
        print("  ERROR: {}".format(e))
        import traceback
        traceback.print_exc()
        return []


# We'll add this method to the Page object
async def extract_all_videos(page):
    """Multiple extraction strategies"""
    # Strategy 1: Direct <a> tags with /video/ in href
    result = await page.evaluate('''() => {
        var results = [], seen = new Set();
        document.querySelectorAll('a[href*="/video/"]').forEach(function(a) {
            var m = a.href.match(/video\\/(\\d+)/);
            if (!m || seen.has(m[1])) return;
            seen.add(m[1]);
            var text = (a.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 200);
            results.push({ id: m[1], title: text, strategy: "a_tag" });
        });
        return results.slice(0, 15);
    }''')
    if result and len(result) > 0:
        print("  Strategy 1 (a tags): {} videos".format(len(result)))
        return result

    # Strategy 2: Look for __NEXT_DATA__ or SSR data
    result = await page.evaluate('''() => {
        // Try to find embedded data in script tags
        var scripts = document.querySelectorAll('script');
        for (var s of scripts) {
            var text = s.textContent || "";
            if (text.indexOf("aweme_list") !== -1 || text.indexOf("awemeId") !== -1) {
                return { found: true, snippet: text.substring(0, 500) };
            }
        }
        // Try __NEXT_DATA__
        var nd = document.getElementById("__NEXT_DATA__");
        if (nd) return { found: true, source: "next_data", snippet: nd.textContent.substring(0, 500) };
        return { found: false };
    }''')
    print("  Strategy 2 (embedded data): {}".format(json.dumps(result, ensure_ascii=False)[:200] if result else "null"))

    # Strategy 3: Look for RENDER_DATA or window.__RENDER_DATA__
    result = await page.evaluate('''() => {
        if (window.__RENDER_DATA__) {
            try { return { found: true, data: decodeURIComponent(window.__RENDER_DATA__).substring(0, 1000) }; }
            catch(e) { return { found: true, error: e.message }; }
        }
        return { found: false };
    }''')
    if result and result.get('found'):
        print("  Strategy 3 (RENDER_DATA): FOUND!")
        raw = result.get('data', '') or result.get('snippet', '')
        if raw:
            try:
                data = json.loads(raw)
                return parse_embedded_data(data)
            except:
                pass

    return []


def parse_embedded_data(data):
    """Parse embedded JSON data to extract video list"""
    videos = []
    try:
        # Navigate the complex nested structure
        def find_awemes(obj, depth=0):
            if depth > 15 or not isinstance(obj, dict):
                return
            if 'awemeList' in obj:
                for item in obj.get('awemeList', []):
                    if isinstance(item, dict):
                        aid = str(item.get('awemeId', item.get('aweme_id', '')))
                        desc = item.get('desc', '')
                        stats = item.get('statistics', {}) or {}
                        digg = stats.get('diggCount', 0) or 0
                        if aid:
                            videos.append({'id': aid, 'title': desc[:200], 'likes': digg, 'strategy': 'embedded'})
            for v in obj.values():
                if isinstance(v, dict):
                    find_awemes(v, depth + 1)
                elif isinstance(v, list):
                    for item in v[:3]:
                        if isinstance(item, dict):
                            find_awemes(item, depth + 1)
        find_awemes(data)
    except Exception as e:
        print("  Parse error: {}".format(e))
    return videos


async def main():
    all_results = {}

    async with async_playwright() as p:
        print("Launching Chrome (system browser)...")
        browser = await p.chromium.launch(
            channel='chrome',
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        print("\nVisiting douyin.com...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            print("  Warning: {}".format(e))

        for name, sec_uid in BLOGGERS:
            print("\n=== {} ===".format(name))
            videos = await scrape_blogger(page, name, sec_uid)
            all_results[name] = videos
            await page.wait_for_timeout(2000)

        await browser.close()

    print("\n" + "=" * 50)
    print(json.dumps(all_results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
