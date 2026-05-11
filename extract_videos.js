const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const WORK_DIR = 'C:/Users/Kevin/WorkBuddy/2026-05-08-task-5/hot-info';

async function extractDouyinDesc(page, url) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(6000);
  await page.evaluate(() => window.scrollTo(0, 800));
  await page.waitForTimeout(3000);

  const desc = await page.evaluate(() => {
    const t = document.body.innerText;
    let i = t.indexOf('作者声明');
    if (i < 0) i = t.indexOf('发布时间');
    if (i < 0) return '';
    const s = t.substring(i);
    return s.split('\n')
      .filter(l => l.trim().length > 15 && !/发布时间|粉丝\d|获赞\d|登录|合集|第\d+集|^\d+:/.test(l.trim()))
      .slice(0, 6)
      .join('\n');
  });
  return desc || '';
}

async function extractBilibiliDesc(page, url) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);
  const desc = await page.evaluate(() => {
    const d = document.querySelector('.video-desc,.basic-desc-info,.desc-info-text');
    if (d) return d.textContent.trim();
    const m = document.querySelector('meta[name=description]');
    return m ? m.content : '';
  });
  return desc || '';
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
  });
  const page = await context.newPage();

  // 读取 data.json
  const dataPath = path.join(WORK_DIR, 'data.json');
  const raw = fs.readFileSync(dataPath, 'utf-8');
  // 去掉 BOM
  const json = JSON.parse(raw.charCodeAt(0) === 0xFEFF ? raw.slice(1) : raw);
  const bloggers = json.articles.filter(a => a.source === 'blogger');

  console.log(`共 ${bloggers.length} 条视频\n`);

  let updated = 0;
  for (let i = 0; i < bloggers.length; i++) {
    const v = bloggers[i];
    const url = v.url || '';
    const name = v.blogger_name || '';

    if (!url) { console.log(`[${i+1}/${bloggers.length}] 无URL`); continue; }
    console.log(`[${i+1}/${bloggers.length}] ${name} ${url.substring(0,60)}...`);

    try {
      let desc = '';
      if (url.includes('douyin.com')) {
        desc = await extractDouyinDesc(page, url);
      } else if (url.includes('bilibili.com')) {
        desc = await extractBilibiliDesc(page, url);
      }
      
      if (desc && desc.length > 20 && desc !== v.content_intro) {
        v.content_intro = desc;
        updated++;
        const preview = desc.replace(/\n/g, ' ').substring(0, 100);
        console.log(`  ✅ ${desc.length}字: ${preview}`);
      } else if (desc && desc.length > 20) {
        console.log(`  - 无变化`);
      } else {
        console.log(`  ⚠️ 未提取到文案 (${desc.length}字)`);
      }
    } catch (e) {
      console.log(`  ❌ ${e.message}`);
    }
    console.log();
  }

  await browser.close();

  if (updated > 0) {
    fs.writeFileSync(dataPath, JSON.stringify(json, null, 2), 'utf-8');
    console.log(`✅ ${updated}/${bloggers.length} 条文案已更新，保存到 ${dataPath}`);
  } else {
    console.log(`无更新`);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
