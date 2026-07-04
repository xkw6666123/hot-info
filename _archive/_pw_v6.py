# -*- coding: utf-8 -*-
"""
Playwright v6 - Fix two critical bugs from v5:
1. Tab selection: prioritize "作品" over "喜欢" (was clicking wrong tab)
2. items.push TypeError: ensure items is always a real Array
Plus: better anti-detection + mobile user-agent fallback
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
    m = re.search(r'(\d{2}-\d{2})', date_str)
    if m:
        return f"{now.year}-{m.group(1)}"
    return date_str


def parse_stat(s):
    if not s:
        return 0
    s = s.strip().replace(',', '')
    m = re.match(r'([\d.]+)万?', s)
    if m:
        n = float(m.group(1))
        return int(n * 10000) if '万' in s else int(n)
    return 0


async def extract_videos(page):
    """Extract video data with multiple strategies - v6 fixed version"""
    videos = []

    # Strategy A: RENDER_DATA
    render_data = await page.evaluate("""() => {
        try {
            var rd = window.__RENDER_DATA__;
            if (rd && typeof rd === 'string') return rd;
        } catch(e) {}
        var el = document.querySelector('#__NEXT_DATA__');
        if (el) return el.textContent;
        return null;
    }""")

    if render_data and len(str(render_data)) > 50:
        try:
            rd_text = str(render_data)
            import urllib.parse
            if '%' in rd_text[:20]:
                rd_text = urllib.parse.unquote(rd_text)
            rd = json.loads(rd_text)

            def find_awemes(obj, depth=0):
                results = []
                if depth > 20 or not isinstance(obj, dict):
                    return results
                for key, val in obj.items():
                    if isinstance(val, list) and len(val) > 0:
                        for item in val[:15]:
                            if isinstance(item, dict):
                                vid = item.get('aweme_id') or item.get('id')
                                if vid and str(vid).isdigit() and len(str(vid)) > 10:
                                    stats = item.get('statistics', {}) or {}
                                    results.append({
                                        'id': str(vid),
                                        'desc': item.get('desc', '')[:200],
                                        'likes': stats.get('digg_count', 0) or 0,
                                        'comments': stats.get('comment_count', 0) or 0,
                                        'shares': stats.get('share_count', 0) or 0,
                                        'create_time': item.get('create_time'),
                                    })
                                    if len(results) >= 10:
                                        return results
                    elif isinstance(val, dict):
                        results.extend(find_awemes(val, depth + 1))
                        if len(results) >= 10:
                            return results
                return results

            videos = find_awemes(rd)
            if videos:
                print(f"  [RENDER_DATA] Got {len(videos)} videos!")
                return videos
        except Exception as e:
            print(f"  [RENDER_DATA] Failed: {e}")

    # Strategy B: DOM extraction - V6 FIX: items is always Array, never NodeList
    dom_results = await page.evaluate("""() => {
        var results = [];
        var seen = new Set();

        // Method 1: user-post-list container items
        var container = document.querySelector('[data-e2e="user-post-list"]');
        // V6 FIX: Always convert to Array
        var items = container ? Array.from(container.querySelectorAll(':scope > li')) : [];

        // Method 2: Any <li> inside main content that contains video links
        if (items.length === 0) {
            var collected = [];
            var allLi = document.querySelectorAll('ul li');
            for (var li of allLi) {
                if (li.querySelector('a[href*="/video/"]')) {
                    collected.push(li);
                }
            }
            items = collected; // This is already a real Array
        }

        // Method 3: Direct video links as last resort
        if (items.length === 0) {
            var links = document.querySelectorAll('a[href*="/video/"]');
            items = Array.from(links); // V6 FIX: Convert NodeList to Array
        }

        for (var el of items) {
            var linkEl = (el.tagName === 'A') ? el : el.querySelector('a[href*="/video/"]');
            if (!linkEl) continue;

            var href = linkEl.getAttribute('href') || '';
            var m = href.match(/video\\/(\\d+)/);
            if (!m || seen.has(m[1])) continue;
            seen.add(m[1]);

            // Title extraction
            var title = '';
            var descEl = el.querySelector('[data-e2e="video-desc"], p[data-e2e="video-desc"]');
            if (descEl) title = descEl.textContent.trim();
            if (!title || title.length < 2) {
                var pEls = el.querySelectorAll('p');
                for (var pi = 0; pi < pEls.length; pi++) {
                    var t = pEls[pi].textContent.trim();
                    if (t.length > 5) { title = t; break; }
                }
            }
            if (!title || title.length < 2) {
                title = (el.textContent || '').trim().replace(/\\s+/g, ' ').substring(0, 200);
            }

            // Stats
            var likeText = '', commentText = '', shareText = '', dateText = '';
            var statEls = el.querySelectorAll('[data-e2e*="count"], span[class*="count"]');
            for (var si = 0; si < statEls.length; si++) {
                var se = statEls[si];
                var e2e = se.getAttribute('data-e2e') || '';
                var txt = se.textContent.trim();
                if (e2e.includes('like')) likeText = txt;
                else if (e2e.includes('comment')) commentText = txt;
                else if (e2e.includes('share')) shareText = txt;
            }

            var timeEl = el.querySelector('[data-e2e="video-publish"], time, [class*="time"]');
            if (timeEl) dateText = timeEl.textContent.trim();

            results.push({
                id: m[1],
                title: title.substring(0, 200),
                likesText: likeText,
                commentsText: commentText,
                sharesText: shareText,
                dateText: dateText,
            });
            if (results.length >= 10) break;
        }
        return results;
    }""")

    if dom_results:
        print(f"  [DOM] Got {len(dom_results)} videos")
        for v in dom_results:
            videos.append({
                'id': v['id'],
                'title': v['title'],
                'likes': parse_stat(v.get('likesText', '')),
                'comments': parse_stat(v.get('commentsText', '')),
                'shares': parse_stat(v.get('sharesText', '')),
                'date_text': v.get('dateText', ''),
            })

    return videos


async def scrape_blogger(page, name, sec_uid):
    url = f"https://www.douyin.com/user/{sec_uid}"
    print(f"\n{'='*55}")
    print(f"=== {name} ===")
    print(f"  Opening...")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)

        # Initial wait for SPA shell to load
        await page.wait_for_timeout(8000)

        title = await page.title()
        print(f"  Title: [{title.strip()[:60]}]")

        # Check we're on a profile page
        body_preview = await page.evaluate("() => document.body.innerText.substring(0, 150)")
        print(f"  Body preview: {body_preview.strip()[:100]}")

        # V6 FIX: Tab selection - prioritize "作品" > "视频" > "喜欢"
        # Build priority map to click the RIGHT tab
        clicked_tab = await page.evaluate("""() => {
            var tabs = document.querySelectorAll('[class*="tab"], [role="tab"], [data-e2e*="tab"]');
            var bestTab = null;
            var bestPriority = 999;

            for (var t of tabs) {
                var text = t.textContent.trim();
                // Priority order: 作品=1, 视频=2, 喜欢=99 (avoid!)
                var priority;
                if (text === '作品') priority = 1;
                else if (text === '视频') priority = 2;
                else if (text === '喜欢') priority = 99;
                else continue;

                if (priority < bestPriority) {
                    bestPriority = priority;
                    bestTab = t;
                }
            }

            if (bestTab) {
                bestTab.click();
                return bestTab.textContent.trim();
            }
            return null;
        }""")
        if clicked_tab:
            print(f"  Clicked tab: [{clicked_tab}]")
            await page.wait_for_timeout(4000)

        # Aggressive scrolling strategy with progress tracking
        prev_count = 0
        stale_rounds = 0

        for scroll_round in range(12):  # Up to 12 rounds
            scroll_amount = 2000 + scroll_round * 500
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await page.wait_for_timeout(3000)

            post_list_count = await page.evaluate("""() => {
                var c = document.querySelector('[data-e2e="user-post-list"]');
                return c ? c.querySelectorAll(':scope > li').length : 0;
            }""")
            video_links = await page.evaluate("() => document.querySelectorAll('a[href*=\"/video/\"]').length")

            if scroll_round % 3 == 0 or post_list_count > 0:
                print(f"  Scroll #{scroll_round+1}: postList_li={post_list_count}, video_links={video_links}")

            if post_list_count >= 3 or video_links >= 5:
                print(f"  Videos found after {scroll_round+1} scrolls!")
                break

            # Track stale rounds
            if video_links == prev_count:
                stale_rounds += 1
            else:
                stale_rounds = 0

            prev_count = video_links

            # If no progress for 3+ rounds, try alternative scroll methods
            if stale_rounds >= 3 and scroll_round > 3:
                # Try mouse wheel simulation
                await page.evaluate("""() => {
                    window.dispatchEvent(new WheelEvent('wheel', {deltaY: 5000, bubbles: true}));
                }""")
                await page.wait_for_timeout(2000)

                # Try pressing PageDown
                try:
                    await page.keyboard.press("PageDown")
                    await page.wait_for_timeout(2000)
                except:
                    pass

        # Fallback: slow scroll if still nothing
        final_video_links = await page.evaluate("() => document.querySelectorAll('a[href*=\"/video/\"]').length")
        if final_video_links == 0:
            print(f"  Trying slow scroll fallback...")
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(2000)

            for i in range(25):
                await page.evaluate("window.scrollBy(0, 300)")
                await page.wait_for_timeout(1200)
                vc = await page.evaluate("() => document.querySelectorAll('a[href*=\"/video/\"]').length")
                if vc > 0:
                    print(f"  Found {vc} video links at slow-scroll step {i+1}")
                    break

        # Extract whatever we found
        videos = await extract_videos(page)
        results = []

        for v in videos:
            vid = v.get('id', '')
            if not vid:
                continue

            create_time = v.get('create_time')
            if create_time and isinstance(create_time, (int, float)):
                try:
                    dt = datetime.fromtimestamp(create_time, tz=CST)
                    date_parsed = dt.strftime("%Y-%m-%d")
                except:
                    date_parsed = ""
            else:
                date_parsed = parse_dy_date(v.get('date_text', ''))

            results.append({
                'aweme_id': vid,
                'desc': v.get('title', '')[:200],
                'title': v.get('title', '')[:200],
                'likes': v.get('likes', 0),
                'comments': v.get('comments', 0),
                'shares': v.get('shares', 0),
                'date': date_parsed,
            })
            print(f"  [{len(results)}] id={vid} date={date_parsed} likes={v.get('likes',0)} "
                  f"c={v.get('comments',0)} | {v.get('title','')[:60]}")

        return results

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []


async def main():
    all_results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel='chrome',
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-background-networking',
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
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        """)
        page = await context.new_page()

        # Warm up on douyin home
        print("Warming up...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(4000)
        except Exception as e:
            print(f"  Warmup warning: {e}")

        for name, sec_uid in BLOGGERS:
            videos = await scrape_blogger(page, name, sec_uid)
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
            for v in vids[:3]:
                print(f"      - {v.get('date','?')} | {v.get('title','?')[:50]}")

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_scrape_v6_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {output_file}")


if __name__ == '__main__':
    asyncio.run(main())
