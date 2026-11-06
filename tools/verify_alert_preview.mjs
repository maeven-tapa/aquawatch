import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.AQUAWATCH_PLAYWRIGHT_MODULE||'playwright');
const base=process.env.AQUAWATCH_PREVIEW_URL||'http://127.0.0.1:8002';
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const fixture=JSON.parse(await fs.readFile(process.env.AQUAWATCH_PREVIEW_SESSION_FILE,'utf8'));
const browser=await chromium.launch({headless:true,executablePath:process.env.AQUAWATCH_CHROME_PATH});
const context=await browser.newContext({viewport:{width:390,height:844}});
await context.addCookies([{name:'sessionid',value:fixture.sessionid,url:base}]);
const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
async function sync(kind,data,id=crypto.randomUUID()){
  const response=await context.request.post(`${base}/api/v1/sync/`,{headers:{'Authorization':`Bearer ${fixture.token}`},data:{events:kind?[{id,kind,data}]:[]}});
  assert.equal(response.status(),200,await response.text());return response.json();
}
try{
  const time=Date.now()-1000;
  const reading={device_id:'preview-phone',received_at:time,latitude:14.41,longitude:120.78,alert_type:'SOS',is_distress:true};
  await sync('reading.create',reading);
  await page.goto(`${base}/alerts/`);await page.locator('[data-alert-id]').first().waitFor();
  assert.equal(await page.locator('[data-alert-id]').count(),1);
  assert.ok((await page.locator('#alerts-list').innerText()).includes('Browser alert verification boat'));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  if(process.env.AQUAWATCH_PREVIEW_ARTIFACTS){await fs.mkdir(process.env.AQUAWATCH_PREVIEW_ARTIFACTS,{recursive:true});await page.screenshot({path:`${process.env.AQUAWATCH_PREVIEW_ARTIFACTS}/alerts-mobile.png`,fullPage:true});}
  await page.getByRole('button',{name:'Dismiss',exact:true}).click();
  await page.getByText('No active alerts',{exact:true}).waitFor();
  const dismissed=await sync();assert.equal(dismissed.snapshot.alerts.length,0);
  assert.ok(dismissed.snapshot.dismissed_alert_ids.includes(`preview-phone-${time}`));
  const next={...reading,received_at:time+1,alert_type:'Gyro tilt',is_distress:false};
  await sync('reading.create',next);
  await page.getByRole('button',{name:'Refresh',exact:true}).click();
  await page.getByText('Gyro tilt',{exact:true}).waitFor();
  await sync('alert.dismiss',{alert_id:`preview-phone-${time+1}`});
  await page.getByRole('button',{name:'Refresh',exact:true}).click();
  await page.getByText('No active alerts',{exact:true}).waitFor();
  await sync('alert.create',next);
  await page.reload();await page.getByText('No active alerts',{exact:true}).waitFor();
  if(process.env.AQUAWATCH_PREVIEW_ARTIFACTS)await page.screenshot({path:`${process.env.AQUAWATCH_PREVIEW_ARTIFACTS}/alerts-dismissed-mobile.png`,fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Passed: phone upload → web alert → browser dismissal → phone sync; phone dismissal → web refresh; no resurrection after backfill; narrow layout.');
} finally{await browser.close();}
