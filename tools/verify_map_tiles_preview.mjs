// Verify browser-generated tile headers and blocked-tile behavior without
// downloading tiles from the public volunteer service.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.AQUAWATCH_PLAYWRIGHT_MODULE||'playwright');
const base=process.env.AQUAWATCH_PREVIEW_URL||'http://127.0.0.1:8002';
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const session=JSON.parse(await fs.readFile(process.env.AQUAWATCH_PREVIEW_SESSION_FILE,'utf8'));
const browser=await chromium.launch({headless:true,executablePath:process.env.AQUAWATCH_CHROME_PATH});
const context=await browser.newContext({viewport:{width:1280,height:900}});
await context.addCookies([{name:'sessionid',value:session.sessionid,url:base}]);
const page=await context.newPage(),headers=[],errors=[];let block=false;
page.on('pageerror',e=>errors.push(e.message));
await page.route('https://tile.openstreetmap.org/**',async route=>{
  headers.push(await route.request().allHeaders());
  if(block)await route.fulfill({status:403,body:'Access blocked'});
  else await route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==','base64')});
});
try{
  const response=await page.goto(`${base}/map/?month=2026-11`);
  assert.equal(response.headers()['referrer-policy'],'strict-origin-when-cross-origin');
  await page.waitForFunction(()=>[...document.querySelectorAll('img.leaflet-tile')].some(i=>i.complete&&i.naturalWidth));
  assert.ok(headers.length>0);
  headers.forEach(h=>assert.equal(h.referer,new URL(base).origin+'/'));
  const policy=await page.locator('img.leaflet-tile').first().getAttribute('referrerpolicy');
  assert.equal(policy,'strict-origin-when-cross-origin');
  assert.equal(await page.locator('.fish-map-marker').count(),10);
  assert.ok(!(await page.locator('.map-tile-status').first().isVisible()));
  block=true;await page.reload();
  await page.locator('.map-tile-status').first().waitFor({state:'visible'});
  assert.equal(await page.locator('.fish-map-marker').count(),10);
  assert.equal(await page.locator('img.leaflet-tile[src^="data:image/svg+xml"]').count()>0,true);
  await page.locator('.habitat-area-choice').first().click();
  assert.equal(await page.locator('.habitat-fish-card').count(),6);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  const {message,month}=await page.evaluate(()=>({message:document.querySelector('.map-tile-status').getBoundingClientRect().toJSON(),month:document.querySelector('.month-map-control').getBoundingClientRect().toJSON()}));
  assert.ok(message.y+message.height<=month.y || message.x+message.width<=month.x,`Tile failure message must not overlap month navigation: ${JSON.stringify({message,month,margin:await page.locator('.map-tile-status').first().evaluate(e=>getComputedStyle(e).marginBottom)})}`);
  assert.deepEqual(errors,[]);
  if(process.env.AQUAWATCH_PREVIEW_ARTIFACTS){await fs.mkdir(process.env.AQUAWATCH_PREVIEW_ARTIFACTS,{recursive:true});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`${process.env.AQUAWATCH_PREVIEW_ARTIFACTS}/map-tile-fallback.png`,fullPage:false});}
  console.log('Passed: origin-only Referer, per-image referrer policy, 403 fallback, 10 fishing markers, usable habitat guides, narrow layout. No public tile traffic.');
}finally{await browser.close();}
