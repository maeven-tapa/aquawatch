import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.AQUAWATCH_PLAYWRIGHT_MODULE||'playwright');
const base=process.env.AQUAWATCH_PREVIEW_URL||'http://127.0.0.1:8002';
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const fixture=JSON.parse(await fs.readFile(process.env.AQUAWATCH_PREVIEW_SESSION_FILE,'utf8'));
const browser=await chromium.launch({headless:true,executablePath:process.env.AQUAWATCH_CHROME_PATH});
const context=await browser.newContext();
await context.addCookies([{name:'sessionid',value:fixture.sessionid,url:base}]);
const page=await context.newPage(),errors=[];
page.on('pageerror',error=>errors.push(error.message));
async function sync(kind,data){
  const response=await context.request.post(`${base}/api/v1/sync/`,{
    headers:{Authorization:`Bearer ${fixture.token}`},
    data:{events:kind?[{id:crypto.randomUUID(),kind,data}]:[]}
  });
  assert.equal(response.status(),200,await response.text());
  return response.json();
}
try{
  await page.goto(`${base}/devices/`);
  assert.equal(await page.locator('#live-revision').count(),1);
  await sync('device.upsert',{id:'auto-sync-phone',name:'Amaya Automatic Sync Tracker',serial:'AW-AUTO-SYNC',type:'GPS tracker',sim:'+639171234569'});
  await page.getByText('Amaya Automatic Sync Tracker',{exact:true}).first().waitFor({timeout:20000});
  await sync('device.upsert',{id:'auto-sync-phone',name:'Amaya Updated Tracker',serial:'AW-AUTO-SYNC',type:'GPS tracker',sim:'+639171234569'});
  await page.getByText('Amaya Updated Tracker',{exact:true}).first().waitFor({timeout:20000});
  await page.goto(`${base}/alerts/`);
  await page.getByText('No active alerts',{exact:true}).waitFor();
  const received=Date.now()-1000;
  await sync('reading.create',{device_id:'auto-sync-phone',received_at:received,latitude:14.41,longitude:120.78,alert_type:'SOS',is_distress:true});
  await page.getByText('SOS',{exact:true}).waitFor({timeout:12000});
  assert.ok((await page.locator('#alerts-list').innerText()).includes('Amaya Updated Tracker'));
  await sync('alert.dismiss',{alert_id:`auto-sync-phone-${received}`});
  await page.getByText('No active alerts',{exact:true}).waitFor({timeout:12000});
  const state=await sync();
  assert.equal(state.snapshot.alerts.length,0);
  assert.ok(state.snapshot.dismissed_alert_ids.includes(`auto-sync-phone-${received}`));
  assert.deepEqual(errors,[]);
  console.log('Passed: device creation and edit appear automatically; new SMS-style SOS appears automatically; mobile dismissal clears web automatically; no manual refresh and no browser errors.');
}finally{await browser.close();}
