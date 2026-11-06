// Read-only UI checks against an isolated local preview account.
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.AQUAWATCH_PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.AQUAWATCH_PREVIEW_URL || 'http://127.0.0.1:8001';
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname),'Use an isolated local preview');
const artifacts=process.env.AQUAWATCH_PREVIEW_ARTIFACTS;
if(artifacts) await mkdir(artifacts,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.AQUAWATCH_CHROME_PATH || undefined});
const page=await browser.newPage({viewport:{width:1280,height:900}});
// Do not drive public OSM tile traffic from automated pan/zoom checks. Human
// browsers load the normal attributed tiles; this test exercises the overlays.
await page.route('https://tile.openstreetmap.org/**',route=>route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==','base64')}));
const errors=[];page.on('pageerror',error=>errors.push(error.message));
async function capture(name) {if(artifacts) {await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(artifacts,name),fullPage:true});}}
try {
  await page.goto(`${base}/login/`);
  await page.locator('input[name="username"]').fill(process.env.AQUAWATCH_PREVIEW_USER);
  await page.locator('input[name="password"]').fill(process.env.AQUAWATCH_PREVIEW_PASSWORD);
  await Promise.all([page.waitForURL('**/dashboard/'),page.locator('button[type="submit"]').click()]);
  await page.goto(`${base}/map/`);
  await page.locator('.habitat-area-choice').first().waitFor();
  assert.equal(await page.locator('.habitat-area-choice').count(),11);
  await page.locator('.fish-map-marker').first().waitFor();
  assert.equal(await page.locator('.fish-map-marker').count(),11);
  await capture('map-desktop.png');
  await page.locator('.habitat-area-choice').first().click();
  await page.locator('#habitat-title').scrollIntoViewIfNeeded();
  assert.equal(await page.locator('.habitat-fish-card').count(),6);
  assert.ok(!(await page.locator('#habitat-content').innerText()).includes('Regional fish guide'));
  await page.locator('#trip-tab').click();
  await page.waitForFunction(()=>{
    const text=document.querySelector('.trip-result')?.textContent || '';
    return text && !text.includes('Checking tide');
  },undefined,{timeout:30000});
  console.log('Trip forecast:',(await page.locator('.trip-result').innerText()).includes('Forecast unavailable')?'unavailable fallback':'loaded model data');
  await page.locator('#trip-day').selectOption({index:1});
  await page.locator('#trip-phase').selectOption('falling');
  await page.locator('#trip-travel').fill('45');await page.locator('#trip-travel').press('Tab');
  await capture('trip-desktop.png');
  await page.setViewportSize({width:390,height:844});
  await page.locator('#habitat-panel').scrollIntoViewIfNeeded();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Map page overflows on a narrow screen');
  await capture('trip-mobile.png');
  await page.goto(`${base}/devices/1/`);
  assert.equal(await page.locator('.sample-badge').count(),33);
  assert.equal(await page.locator('.device-log-badge').count(),1);
  await page.locator('#history-from').fill('2026-10-16');await page.locator('#history-from').press('Tab');
  await page.locator('#history-to').fill('2026-10-16');await page.locator('#history-to').press('Tab');
  await page.locator('#history-source').selectOption('sample');
  assert.equal(await page.locator('#history-rows tr:visible').count(),3);
  await page.locator('#history-reset').click();
  await page.locator('#history-source').selectOption('device');
  assert.equal(await page.locator('#history-rows tr:visible').count(),1);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'History page overflows on a narrow screen');
  await capture('history-mobile.png');
  await page.locator('#history-reset').click();
  await page.setViewportSize({width:1280,height:900});
  await capture('history-desktop.png');
  assert.deepEqual(errors,[],'Unexpected browser JavaScript errors');
  console.log('Browser checks passed: 11 areas, 6 fish, trip controls, 33 samples, real logs, filters, narrow layouts.');
} finally {await browser.close();}
