// Exercise admin editing against an explicitly local preview only.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.AQUAWATCH_PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.AQUAWATCH_PREVIEW_URL || 'http://127.0.0.1:8002';
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const session=JSON.parse(await fs.readFile(process.env.AQUAWATCH_PREVIEW_SESSION_FILE,'utf8'));
const folder=process.env.AQUAWATCH_PREVIEW_ARTIFACTS;
if(folder)await fs.mkdir(folder,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.AQUAWATCH_CHROME_PATH});
const context=await browser.newContext({viewport:{width:1280,height:900}});
await context.addCookies([{name:'sessionid',value:session.sessionid,url:base}]);
await context.route('https://tile.openstreetmap.org/**',r=>r.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==','base64')}));
const page=await context.newPage(),errors=[];
let lastSave;
await page.route('**/fishing-zones/**',async route=>{
  if(route.request().method()!=='POST')return route.continue();
  const response=await route.fetch();lastSave={status:response.status(),data:await response.json()};
  await route.fulfill({response});
});
page.on('pageerror',e=>errors.push(e.message));
let created;
async function capture(name){if(folder)await page.screenshot({path:`${folder}/${name}.png`,fullPage:true});}
try {
  await page.goto(`${base}/map/?month=2026-11`);
  await page.locator('.fish-map-marker').first().waitFor();
  assert.equal(await page.locator('.fish-map-marker').count(),10);
  assert.ok(await page.locator('.site-nav').getByText('Users',{exact:true}).isVisible());
  assert.equal(await page.locator('.site-nav a').count(),5);
  await capture('admin-map-desktop');
  await page.getByRole('link',{name:'Previous month',exact:true}).click();
  await page.locator('.fish-map-marker').first().waitFor();
  assert.equal(await page.locator('.fish-map-marker').count(),16);
  await page.locator('#new-fishing-zone').click();
  await page.locator('#zone-name').fill('UI verification zone');
  await page.locator('#zone-month').fill('2027-01');
  const saveResponse=page.waitForResponse(r=>r.url()===`${base}/fishing-zones/`&&r.request().method()==='POST');
  await page.locator('#save-zone').click();
  const result=await saveResponse;
  assert.equal(result.status(),200,JSON.stringify(lastSave));created=lastSave.data.zone;
  await page.waitForURL('**/map/?month=2027-01');
  await page.locator(`[data-zone-id="${created.id}"]`).click();
  await page.getByRole('button',{name:'Edit location, size and shape'}).click();
  await page.locator('#zone-scale').fill('110');
  await page.getByRole('button',{name:'Apply size',exact:true}).click();
  await capture('admin-zone-editor-desktop');
  const edited=page.waitForResponse(r=>r.url()===`${base}/fishing-zones/${created.id}/`&&r.request().method()==='POST');
  await page.locator('#save-zone').click();
  const response=await edited;assert.equal(response.status(),200,JSON.stringify(lastSave));
  const changed=lastSave.data.zone;
  assert.equal(changed.version,2);assert.ok(changed.area_square_meters>created.area_square_meters*1.2);
  await page.waitForURL('**/map/?month=2027-01');
  await page.locator(`[data-zone-id="${created.id}"]`).click();
  await page.getByRole('button',{name:'Edit location, size and shape'}).click();
  const vertex=page.locator('#zone-edit-map .zone-vertex-marker').first();
  await vertex.scrollIntoViewIfNeeded();
  const before=await page.locator('#zone-boundary').inputValue(),rect=await vertex.boundingBox();
  await page.mouse.move(rect.x+rect.width/2,rect.y+rect.height/2);await page.mouse.down();
  await page.mouse.move(rect.x+rect.width/2+12,rect.y+rect.height/2+8,{steps:6});await page.mouse.up();
  await page.waitForFunction(previous=>document.getElementById('zone-boundary').value!==previous,before);
  const reshaped=page.waitForResponse(r=>r.url()===`${base}/fishing-zones/${created.id}/`&&r.request().method()==='POST');
  await page.locator('#save-zone').click();assert.equal((await reshaped).status(),200,JSON.stringify(lastSave));
  assert.equal(lastSave.data.zone.version,3);
  await page.goto(`${base}/users/`);await capture('admin-users-desktop');
  await page.goto(`${base}/admin/aquawatch_app/fishingzone/?q=UI+verification+zone`);
  assert.ok((await page.locator('#result_list').innerText()).includes('UI verification zone'));await capture('django-fishing-zones');
  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}/map/?month=2026-11`);await page.locator('.fish-map-marker').first().waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Map overflow on mobile');
  await page.locator('#new-fishing-zone').click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Editor overflow on mobile');
  await capture('admin-zone-editor-mobile');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'passed',createdZoneId:created.id,checks:['admin navigation','month counts','create zone','resize and save','Django admin table','users page','mobile layouts','no browser errors']}));
} finally {
  // Unpublish only the known temporary zone created by this run.
  if(created){
    const response=await context.request.get(`${base}/fishing-zones/?month=2027-01`);
    const latest=(await response.json()).zones.find(z=>z.id===created.id);
    if(latest)await context.request.post(`${base}/fishing-zones/${created.id}/`,{headers:{'X-CSRFToken':(await context.cookies(base)).find(c=>c.name==='csrftoken')?.value||''},data:{...latest,active:false}});
  }
  await browser.close();
}
