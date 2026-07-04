# -*- coding: utf-8 -*-
"""
Playwright Chrome scraper v3 - fixed and working
"""
import asyncio, json, sys, re

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

async def extract_videos(page):
    """Extract video data from page using multiple strategies"""
    # Strategy 1: Use Douyin's data-e2e user-post-list items (most reliable)
    result = await page.evaluate('''() => {
        var results = [];
        var items = document.querySelectorAll('[data-e2e="user-post-list"] li');
        if (items.length === 0) {
            // Fallback: any <a> with /video/ in href
            items = document.querySelectorAll('a[href*="/video/"]');
        }
        var seen = new Set();
        for (var el of items) {
            // Find video ID from href
            var linkEl = (el.tagName === 'A') ? el : el.querySelector('a[href*="/video/"]');
            if (!linkEl) continue;
            var m = linkEl.href.match(/video\\/(\\d+)/);
            if (!m || seen.has(m[1])) continue;
            seen.add(m[1]);

            // Get text content - prefer the p/desc element inside
            var textEl = el.querySelector('p') || el.querySelector('[class*="desc"]') || el;
            var text = (textEl.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 200);
            if (text.length < 2) text = (el.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 200);

            // Try to find stats
            var likesStr = "";
            var statSpans = el.querySelectorAll('span, [class*="count"], [class*="num"]');
            for (var s of statSpans) {
                var t = s.textContent.trim();
                if (/^[\\d.]+万?$/.test(t) || /^\\d+$/.test(t)) { likesStr = t; break; }
            }

            results.push({ id: m[1], title: text, likesText: likesStr });
            if (results.length >= 10) break;
        }
        return results;
    }''')
    return result or []


async def scrape_blogger(page, name, sec_uid):
    url = "https://www.douyin.com/user/{}".format(sec_uid)
    print("  Opening: {} ...".format(url[:60]))

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(10000)

        title = await page.title()
        print("  Title: {}".format(title[:60]))

        # Check for captcha
        if "验证" in title:
            print("  CAPTCHA! Waiting...")
            await page.wait_for_timeout(8000)

        # Quick check
        vcount = await page.evaluate("() => document.querySelectorAll('a[href*=\"video\"]').length")
        print("  Video links: {}".format(vcount))

        if vcount == 0:
            # Scroll to trigger lazy load
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(2000)
            vcount = await page.evaluate("() => document.querySelectorAll('a[href*=\"video\"]').length")
            print("  After scroll: {} video links".format(vcount))

        videos = await extract_videos(page)
        results = []
        for v in (videos or []):
            vid_id = v.get('id', '')
            title_text = v.get('title', '').strip()
            if not vid_id:
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
            print("  [{}] id={} likes={} {}".format(
                len(results), vid_id, likes, title_text[:45]))

        return results
    except Exception as e:
        print("  ERROR: {}".format(e))
        return []


async def main():
    all_results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel='chrome', headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}, locale='zh-CN',
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        page = await context.new_page()

        print("Visiting douyin.com first...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print("  Warning: {}".format(e))

        for name, sec_uid in BLOGGERS:
            print("\n=== {} ===".format(name))
            videos = await scrape_blogger(page, name, sec_uid)
            all_results[name] = videos

        await browser.close()

    print("\n" + "=" * 50)
    total = sum(len(v) for v in all_results.values())
    print("Total videos: {}".format(total))
    print(json.dumps(all_results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
