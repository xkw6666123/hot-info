# -*- coding: utf-8 -*-
"""
Playwright scraper v4 - Enhanced with RENDER_DATA extraction + date parsing
Fixes: 
  - 网吧信息差/陈先生 got recommended videos (not blogger's own)
  - Missing publish dates, comment/share counts
  - Uses __RENDER_DATA__ for reliable data when available
"""
import asyncio, json, sys, re, os
from datetime import datetime, timezone, timedelta

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed")
    sys.exit(1)

CST = timezone(timedelta(hours=8))  # China Standard Time

BLOGGERS = [
    ("网吧信息差", "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv"),
    ("阿七大型纪录片", "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf"),
    ("陈先生", "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF"),
    ("人类观察菌", "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN"),
]


def parse_dy_date(date_str):
    """Parse Douyin date string to YYYY-MM-DD"""
    if not date_str:
        return ""
    date_str = date_str.strip()
    now = datetime.now(CST)

    # "06-08" format (this year)
    m = re.match(r'^(\d{2})-(\d{2})$', date_str)
    if m:
        return f"{now.year}-{m.group(1)}-{m.group(2)}"

    # "2026-06-08" format
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
    if m:
        return date_str

    # "X天前" / "X小时前" / "刚刚"
    m = re.match(r'^(\d+)天前$', date_str)
    if m:
        days = int(m.group(1))
        d = now - timedelta(days=days)
        return d.strftime("%Y-%m-%d")

    m = re.match(r'^(\d+)小时前$', date_str)
    if m:
        hours = int(m.group(1))
        d = now - timedelta(hours=hours)
        return d.strftime("%Y-%m-%d")

    if "刚刚" in date_str or "分钟前" in date_str:
        return now.strftime("%Y-%m-%d")

    # Try extracting from any "MM-DD" pattern
    m = re.search(r'(\d{2}-\d{2})', date_str)
    if m:
        return f"{now.year}-{m.group(1)}"

    return date_str


async def extract_videos_v4(page):
    """
    Multi-strategy video extraction:
    Strategy A: __RENDER_DATA__ (most complete, includes dates)
    Strategy B: DOM extraction (fallback)
    """
    videos = []

    # === Strategy A: Try RENDER_DATA (SSR data embedded by Douyin) ===
    render_data = await page.evaluate('''() => {
        try {
            var rd = window.__RENDER_DATA__;
            if (rd) return rd;
        } catch(e) {}
        // Also try from script tags
        var scripts = document.querySelectorAll('script[id="__NEXT_DATA__"], script[type="application/json"]');
        for (var s of scripts) {
            try { return s.textContent; } catch(e) {}
        }
        return null;
    }''')

    if render_data:
        try:
            # RENDER_DATA is URL-encoded sometimes
            if isinstance(render_data, str) and '%' in str(render_data)[:20]:
                import urllib.parse
                render_data = urllib.parse.unquote(render_data)

            rd = json.loads(render_data) if isinstance(render_data, str) else render_data

            # Navigate the complex RENDER_DATA structure to find user posts
            # The structure varies but typically: ... -> user -> awem -> list
            def find_videos_in_obj(obj, depth=0):
                results = []
                if depth > 15 or not isinstance(obj, dict):
                    return results
                # Look for aweme_list or similar keys
                for key, val in obj.items():
                    if key in ('awemeList', 'aweme_list', 'AwemeList', 'awemes', 'list'):
                        if isinstance(val, list):
                            for item in val[:10]:
                                if isinstance(item, dict):
                                    vid = item.get('aweme_id') or item.get('id') or item.get('awemeId')
                                    if vid:
                                        results.append({
                                            'id': str(vid),
                                            'desc': item.get('desc', ''),
                                            'title': item.get('desc', '')[:200],
                                            'likes': item.get('statistics', {}).get('digg_count', 0) or item.get('likeCount', 0),
                                            'comments': item.get('statistics', {}).get('comment_count', 0) or item.get('commentCount', 0),
                                            'shares': item.get('statistics', {}).get('share_count', 0) or item.get('shareCount', 0),
                                            'create_time': item.get('create_time') or item.get('createTime'),
                                        })
                    elif isinstance(val, dict):
                        results.extend(find_videos_in_obj(val, depth + 1))
                    elif isinstance(val, list):
                        for sub_item in val[:3]:
                            if isinstance(sub_item, dict):
                                results.extend(find_videos_in_obj(sub_item, depth + 1))
                return results

            videos = find_videos_in_obj(rd)
            if videos:
                print(f"  [Strategy A] RENDER_DATA: {len(videos)} videos found!")
                return videos
        except Exception as e:
            print(f"  [Strategy A] Failed: {e}")

    # === Strategy B: DOM extraction (enhanced from v3) ===
    dom_results = await page.evaluate('''() => {
        var results = [];
        var seen = new Set();

        // Primary: user-post-list container
        var container = document.querySelector('[data-e2e="user-post-list"]');
        var items = container ? container.querySelectorAll(':scope > li') : [];

        // Fallback: all video links on the page
        if (items.length === 0) {
            items = document.querySelectorAll('a[href*="/video/"]');
        }

        for (var el of items) {
            var linkEl = (el.tagName === 'A') ? el : el.querySelector('a[href*="/video/"]');
            if (!linkEl) continue;

            var href = linkEl.getAttribute('href') || '';
            var m = href.match(/video\\/(\\d+)/);
            if (!m || seen.has(m[1])) continue;
            seen.add(m[1]);

            // Extract title text
            var textEl = el.querySelector('p[data-e2e="video-desc"]')
                || el.querySelector('p[class*="desc"]')
                || el.querySelector('[class*="content"] p')
                || el.querySelector('p');
            var title = textEl ? (textEl.textContent || "").trim() : "";
            if (title.length < 2) {
                title = (el.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 200);
            }

            // Extract stats (likes, comments, shares)
            var statsDiv = el.querySelector('[class*="stats"], [data-e2e="video-stats"], .play-count, [class*="count"]');
            var likeSpan = el.querySelector('span[data-e2e="like-count"], [class*="like"] span');
            var commentSpan = el.querySelector('span[data-e2e="comment-count"], [class*="comment"] span');
            var shareSpan = el.querySelector('span[data-e2e="share-count"], [class*="share"] span');

            // Date element
            var dateEl = el.querySelector('span[data-e2e="video-publish"], time, [class*="time"], [class*="date"]');

            results.push({
                id: m[1],
                title: title.substring(0, 200),
                likesText: likeSpan ? likeSpan.textContent.trim() : "",
                commentsText: commentSpan ? commentSpan.textContent.trim() : "",
                sharesText: shareSpan ? shareSpan.textContent.trim() : "",
                dateText: dateEl ? dateEl.textContent.trim() : "",
                totalStats: statsDiv ? statsDiv.textContent.trim().replace(/\\s+/g, " ") : ""
            });
            if (results.length >= 10) break;
        }
        return results;
    }''')

    if dom_results:
        print(f"  [Strategy B] DOM: {len(dom_results)} videos found")
        for v in dom_results:
            likes = parse_stat(v.get('likesText', ''))
            videos.append({
                'id': v['id'],
                'title': v['title'],
                'likes': likes,
                'comments': parse_stat(v.get('commentsText', '')),
                'shares': parse_stat(v.get('sharesText', '')),
                'date_text': v.get('dateText', ''),
            })

    return videos


def parse_stat(s):
    """Parse '1.2万' or '1234' to integer"""
    if not s:
        return 0
    s = s.strip().replace(',', '')
    m = re.match(r'([\d.]+)万?', s)
    if m:
        n = float(m.group(1))
        return int(n * 10000) if '万' in s else int(n)
    return 0


async def scrape_blogger(page, name, sec_uid):
    url = f"https://www.douyin.com/user/{sec_uid}"
    print(f"\n{'='*50}")
    print(f"=== {name} ===")
    print(f"  Opening: {url[:60]}...")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await page.wait_for_timeout(8000)

        title = await page.title()
        print(f"  Page title: {title[:60]}")

        # Check for captcha/login wall
        if "验证" in title:
            print("  CAPTCHA detected! Waiting 10s...")
            await page.wait_for_timeout(10000)

        # Verify we're actually on a user profile page
        is_profile = await page.evaluate('''() => {
            // Check for user profile elements
            var hasAvatar = !!document.querySelector('[data-e2e="user-avatar"], .avatar-container, .user-avatar');
            var hasPostList = !!document.querySelector('[data-e2e="user-post-list"]');
            var hasUserInfo = document.body.innerHTML.includes('sec_uid') || document.body.innerHTML.includes('user-info');
            // Check URL matches user page pattern
            var isUserPage = window.location.pathname.includes('/user/');
            return { hasAvatar, hasPostList, hasUserInfo, isUserPage };
        }''')
        print(f"  Profile check: avatar={is_profile.get('hasAvatar')}, postList={is_profile.get('hasPostList')}, userInfo={is_profile.get('hasUserInfo')}")

        # If no post list found, try scrolling to load
        post_count = await page.evaluate('''() => {
            var c = document.querySelector('[data-e2e="user-post-list"]');
            return c ? c.querySelectorAll('li').length : 0;
        }''')
        print(f"  Initial post count: {post_count}")

        if post_count == 0:
            print("  No posts yet, scrolling...")
            for i in range(5):
                await page.evaluate("window.scrollBy(0, 1500)")
                await page.wait_for_timeout(2500)
            post_count = await page.evaluate('''() => {
                var c = document.querySelector('[data-e2e="user-post-list"]');
                return c ? c.querySelectorAll('li').length : 0;
            }''')
            print(f"  After scroll: {post_count} posts")

        # Also try clicking the "视频" tab to ensure we're on video tab
        await page.evaluate('''() => {
            var tabs = document.querySelectorAll('[data-e2e="tab-name"], .tab-item, [class*="tab"]');
            for (var t of tabs) {
                if (t.textContent.trim() === '作品' || t.textContent.trim() === '视频') {
                    t.click();
                    break;
                }
            }
        }''')
        await page.wait_for_timeout(3000)

        videos = await extract_videos_v4(page)
        results = []
        for v in (videos or []):
            vid_id = v.get('id', '')
            if not vid_id:
                continue
            title_text = v.get('title', '') or v.get('desc', '')
            date_text = v.get('date_text', '')

            # Parse create_time timestamp if available
            create_time = v.get('create_time')
            if create_time and isinstance(create_time, (int, float)):
                try:
                    dt = datetime.fromtimestamp(create_time, tz=CST)
                    date_parsed = dt.strftime("%Y-%m-%d")
                except:
                    date_parsed = ""
            else:
                date_parsed = parse_dy_date(date_text)

            results.append({
                'aweme_id': vid_id,
                'desc': title_text[:200],
                'title': title_text[:200],
                'likes': v.get('likes', 0) or 0,
                'comments': v.get('comments', 0) or 0,
                'shares': v.get('shares', 0) or 0,
                'date': date_parsed,
                'date_raw': date_text,
            })
            print(f"  [{len(results)}] id={vid_id} date={date_parsed} likes={v.get('likes',0)} "
                  f"c={v.get('comments',0)} s={v.get('shares',0)} | {title_text[:50]}")

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
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
            # Use larger viewport to avoid mobile layout issues
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)
        page = await context.new_page()

        # Warm up on douyin homepage first
        print("Warming up on douyin.com...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  Warmup warning: {e}")

        for name, sec_uid in BLOGGERS:
            videos = await scrape_blogger(page, name, sec_uid)
            all_results[name] = videos

        await browser.close()

    print("\n" + "=" * 60)
    total = sum(len(v) for v in all_results.values())
    print(f"TOTAL: {total} videos from {len(all_results)} bloggers")
    for name, videos in all_results.items():
        print(f"  {name}: {len(videos)} videos")
        if videos:
            latest = max(v.get('date','') for v in videos)
            print(f"    Latest date: {latest}")

    # Save results
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_scrape_v4_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {output_file}")
    print(json.dumps(all_results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
