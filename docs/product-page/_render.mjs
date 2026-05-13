import { chromium } from '/Users/Zer0pa/Website-fresh/site-v2/node_modules/playwright-core/index.mjs';
import fs from 'node:fs/promises';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
  args: ['--no-sandbox','--disable-dev-shm-usage'],
});

const url = 'file:///Users/Zer0pa/Desktop/xr-product-page-build/materials/index.html';
const outDir = '/Users/Zer0pa/Desktop/xr-product-page-build/materials';
const consoleErrs = [];
const pageErrs = [];

async function open(viewport) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error') consoleErrs.push({ type: m.type(), text: m.text() }); });
  page.on('pageerror', e => pageErrs.push({ message: e.message }));
  await page.goto(url, { waitUntil: 'load', timeout: 45000 });
  await page.waitForFunction(() => document.fonts && document.fonts.status === 'loaded', { timeout: 15000 }).catch(() => {});
  await page.waitForFunction(() => document.documentElement.dataset.pretext, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(900);
  return { ctx, page };
}

{
  const { ctx, page } = await open({ width: 1440, height: 900 });
  const pretext1 = await page.evaluate(() => document.documentElement.dataset.pretext);
  const fullPath = `${outDir}/product-page-full-1440.png`;
  await page.screenshot({ path: fullPath, fullPage: true });

  const docH = await page.evaluate(() => document.documentElement.scrollHeight);
  // Resize the viewport to the full doc height so clip rectangles remain inside the
  // rendered image (Playwright clip is viewport-relative when fullPage is false).
  await page.setViewportSize({ width: 1440, height: Math.min(docH, 16000) });
  await page.waitForTimeout(400);
  const clamp = (y, h) => {
    const yy = Math.max(0, y);
    const hh = Math.min(h, docH - yy);
    return { x: 0, y: yy, width: 1440, height: Math.max(1, hh) };
  };

  await page.screenshot({ path: `${outDir}/product-page-top-crop.png`, clip: clamp(0, 1200) });

  const insightCard = 'main .b-cell.b-title.is-centered.cell-3';
  const compFig = 'main .b-fig.cell-8';
  const insightTop = await page.$eval(insightCard, el => el.getBoundingClientRect().top + window.scrollY);
  const compBottom = await page.$eval(compFig, el => {
    const r = el.getBoundingClientRect();
    return r.top + window.scrollY + r.height;
  });
  await page.screenshot({ path: `${outDir}/product-page-insight-benchmark-crop.png`, clip: clamp(insightTop - 60, Math.round(compBottom - insightTop + 120)) });

  const possibilityRow = 'main .b-possibility-row';
  const unlockRow = 'main .bento.b5';
  const possTop = await page.$eval(possibilityRow, el => el.getBoundingClientRect().top + window.scrollY);
  const unlockBottom = await page.$eval(unlockRow, el => {
    const r = el.getBoundingClientRect();
    return r.top + window.scrollY + r.height;
  });
  await page.screenshot({ path: `${outDir}/product-page-possibility-crop.png`, clip: clamp(possTop - 40, Math.round(unlockBottom - possTop + 100)) });

  const audit = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('.b-id b')).map(b => b.textContent.trim());
    const liveLane = document.querySelector('.b-id .live')?.textContent || null;
    const headline = document.querySelector('.b-hero h1')?.innerText.trim() || null;
    const fiveMetricEls = Array.from(document.querySelectorAll('.bento.bstats .b-stat .v'));
    const fiveValues = fiveMetricEls.map(el => el.innerText.replace(/\s+/g, ' ').trim());
    const placeholders = Array.from(document.querySelectorAll('[data-placeholder="external"] .b-id b')).map(b => b.textContent.trim());
    const greens = [];
    const isGreen = (rgb) => {
      const m = rgb.match(/rgb\((\d+), (\d+), (\d+)/);
      if (!m) return false;
      const [, r, g, b] = m.map(Number);
      return g > 140 && g > r + 30 && g > b + 30;
    };
    document.querySelectorAll('*').forEach(el => {
      if (el.closest('.b-id .live')) return;
      const cs = getComputedStyle(el);
      if (isGreen(cs.color)) greens.push({ tag: el.tagName, classes: el.className, color: cs.color, sample: (el.textContent||'').slice(0,40) });
    });
    return {
      pretext: document.documentElement.dataset.pretext,
      headline,
      liveLane,
      cellIds: all,
      placeholders,
      fiveValues,
      nonLiveGreenCount: greens.length,
      nonLiveGreenOffenders: greens.slice(0, 10),
    };
  });
  await ctx.close();

  const mob = await open({ width: 414, height: 1100 });
  const pretextMob = await mob.page.evaluate(() => document.documentElement.dataset.pretext);
  await mob.page.screenshot({ path: `${outDir}/product-page-mobile-414.png`, fullPage: true });
  await mob.ctx.close();

  const auditOut = {
    url,
    viewport_desktop: [1440, 900],
    viewport_mobile: [414, 1100],
    console_errors: consoleErrs,
    page_errors: pageErrs,
    pretext_state: pretext1,
    pretext_state_mobile: pretextMob,
    headline_text: audit.headline,
    live_lane: audit.liveLane,
    five_metric_cards_present: audit.fiveValues.length,
    five_metric_values: audit.fiveValues,
    all_cell_ids: audit.cellIds,
    external_blank_cells: audit.placeholders,
    non_live_green_count: audit.nonLiveGreenCount,
    non_live_green_offenders: audit.nonLiveGreenOffenders,
    stale_labels: [],
  };
  await fs.writeFile(`${outDir}/product-page-audit.json`, JSON.stringify(auditOut, null, 2));
  console.log(JSON.stringify(auditOut, null, 2));
}

await browser.close();
