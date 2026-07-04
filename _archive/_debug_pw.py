# -*- coding: utf-8 -*-
import asyncio, json
from playwright.async_api import async_playwright

async def debug_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel='chrome',
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--disable-gpu']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN'
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        page = await context.new_page()

        # Test with 网吧信息差
        url = 'https://www.douyin.com/user/MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv'
        print(f'Opening...')
        resp = await page.goto(url, wait_until='domcontentloaded', timeout=35000)
        print(f'Status: {resp.status if resp else "no response"}')

        for i in range(6):
            await page.wait_for_timeout(5000)
            info = await page.evaluate("""() => {
                var bodyText = document.body.innerText.substring(0, 200);
                var videoLinks = document.querySelectorAll('a[href*="/video/"]').length;
                return {bodyLen: bodyText.length, videoLinks: videoLinks, preview: bodyText};
            }""")
            print(f"  [{i*5+5}s] body_len={info['bodyLen']} video_links={info['videoLinks']} preview={info['preview'][:100]}")
            if info['videoLinks'] > 3:
                break

        checks = await page.evaluate("""() => ({
            postList: !!document.querySelector('[data-e2e="user-post-list"]'),
            postListLi: document.querySelectorAll('[data-e2e="user-post-list"] li').length,
            videoLinks: document.querySelectorAll('a[href*="/video/"]').length,
            hasRenderData: !!window.__RENDER_DATA__,
            allText: document.body.innerText.substring(0, 1000),
            url: window.location.href
        })""")
        print(json.dumps(checks, ensure_ascii=False, indent=2))

        await browser.close()

asyncio.run(debug_page())
