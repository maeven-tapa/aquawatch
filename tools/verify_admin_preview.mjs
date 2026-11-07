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
let created,adminCreated;
async function capture(name){if(folder)await page.screenshot({path:`${folder}/${name}.png`,fullPage:true});}
try {
  await page.goto(`${base}/map/?month=2026-11`);
  await page.locator('.fish-map-marker').first().waitFor();
  assert.equal(await page.locator('.fish-map-marker').count(),10);
  await page.locator('#zone-month-filter [name=month]').fill('2027-11');
  await page.getByRole('button',{name:'View month',exact:true}).click();
  await page.waitForURL('**/map/?month=2027-11');
  await page.locator('.fish-map-marker').first().waitFor();
  assert.equal(await page.locator('.fish-map-marker').count(),10);
  await page.locator('[data-zone-id]').first().click();
  await page.getByText('Zone date: November 1, 2027',{exact:true}).waitFor();
  await page.getByText('Repeats every year · Original zone date: November 1, 2026',{exact:true}).waitFor();
  await capture('next-year-november');
  await page.goto(`${base}/map/?month=2026-11`);
  assert.ok(await page.locator('.site-nav').getByText('Users',{exact:true}).isVisible());
  assert.equal(await page.locator('.site-nav a').count(),5);
  await capture('admin-map-desktop');
  await page.getByRole('link',{name:'Previous month',exact:true}).click();
  await page.locator('.fish-map-marker').first().waitFor();
  assert.equal(await page.locator('.fish-map-marker').count(),16);
  await page.locator('#new-fishing-zone').click();
  await page.locator('#zone-name').fill('UI verification zone');
  await page.locator('#zone-date').fill('2027-01-17');
  const saveResponse=page.waitForResponse(r=>r.url()===`${base}/fishing-zones/`&&r.request().method()==='POST');
  await page.locator('#save-zone').click();
  const result=await saveResponse;
  assert.equal(result.status(),200,JSON.stringify(lastSave));created=lastSave.data.zone;
  await page.waitForURL('**/map/?month=2027-01');
  await page.locator(`[data-zone-id="${created.id}"]`).click();
  assert.equal(created.date,'2027-01-17');
  assert.ok(created.published_at);
  await page.getByText('Zone date: January 17, 2027',{exact:true}).waitFor();
  await page.getByText(/^First published:/).waitFor();
  await page.getByRole('button',{name:'Edit location, size and shape'}).click();
  await page.locator('#zone-scale').fill('110');
  await page.getByRole('button',{name:'Apply size',exact:true}).click();
  await capture('admin-zone-editor-desktop');
  const edited=page.waitForResponse(r=>r.url()===`${base}/fishing-zones/${created.id}/`&&r.request().method()==='POST');
  const editNavigation=page.waitForNavigation({waitUntil:'domcontentloaded'});
  await page.locator('#save-zone').click();
  const response=await edited;assert.equal(response.status(),200,JSON.stringify(lastSave));
  await editNavigation;
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
  const reshapeNavigation=page.waitForNavigation({waitUntil:'domcontentloaded'});
  await page.locator('#save-zone').click();assert.equal((await reshaped).status(),200,JSON.stringify(lastSave));
  await reshapeNavigation;
  assert.equal(lastSave.data.zone.version,3);
  await page.goto(`${base}/users/`);await capture('admin-users-desktop');
  await page.goto(`${base}/admin/aquawatch_app/fishingzone/?q=UI+verification+zone`);
  assert.ok((await page.locator('#result_list').innerText()).includes('UI verification zone'));await capture('django-fishing-zones');
  await page.goto(`${base}/admin/aquawatch_app/fishingzone/add/`);
  await page.locator('#admin-zone-map .leaflet-control-zoom').waitFor();
  assert.equal(await page.locator('#admin-zone-status').textContent(),'');
  await page.locator('#id_title').fill('Django UI verification zone');
  await page.locator('#id_date').fill('2027-02-19');
  await page.locator('#id_latitude').fill('14.41');
  await page.locator('#id_longitude').fill('120.78');
  await page.locator('#id_boundary').fill(JSON.stringify([
    {lat:14.394717564146315,lng:120.82617223262787},
    {lat:14.395039716406593,lng:120.82710564136507},
    {lat:14.394364235326302,lng:120.82799613475801},
    {lat:14.39406286618496,lng:120.82693397998811}
  ]));
  await page.locator('[name=_save]').click();
  await page.getByText(/Boundary point 1 .*outside the configured offshore/).waitFor();
  assert.equal(await page.locator('#id_date').inputValue(),'2027-02-19');
  await page.locator('#admin-zone-starter').click();
  await page.locator('#id_latitude').fill('14.45');
  await page.locator('#admin-zone-center').click();
  assert.ok(Number(await page.locator('#id_latitude').inputValue())<14.413);
  await capture('django-zone-repaired');
  await page.locator('[name=_save]').click();
  await page.waitForURL('**/admin/aquawatch_app/fishingzone/');
  const adminZones=await context.request.get(`${base}/fishing-zones/?month=2027-02`);
  adminCreated=(await adminZones.json()).zones.find(z=>z.title==='Django UI verification zone'&&z.active);
  assert.equal(adminCreated?.date,'2027-02-19');
  assert.ok(adminCreated.published_at);
  await page.goto(`${base}/map/?month=2027-02`);
  await page.locator(`[data-zone-id="${adminCreated.id}"]`).click();
  await page.getByText('Zone date: February 19, 2027',{exact:true}).waitFor();
  await page.getByText(/^First published:/).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}/map/?month=2026-11`);await page.locator('.fish-map-marker').first().waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Map overflow on mobile');
  await page.locator('#new-fishing-zone').click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Editor overflow on mobile');
  await capture('admin-zone-editor-mobile');
  await page.goto(`${base}/admin/aquawatch_app/fishingzone/add/`);
  await page.locator('#admin-zone-map .leaflet-control-zoom').waitFor();
  assert.equal(await page.locator('#admin-zone-status').textContent(),'');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Django admin editor overflow on mobile');
  await capture('django-zone-editor-mobile');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'passed',createdZoneId:created.id,checks:['admin navigation','original monthly zone counts','November 2027 recurrence','exact dates','publication details','resize and save','Django admin boundary error and repair','Django admin create','users page','mobile layouts','no browser errors']}));
} finally {
  // Unpublish only the known temporary zone created by this run.
  for(const zone of [created,adminCreated].filter(Boolean)){
    const response=await context.request.get(`${base}/fishing-zones/?month=${zone.month}`);
    const latest=(await response.json()).zones.find(z=>z.id===zone.id);
    if(latest)await context.request.post(`${base}/fishing-zones/${zone.id}/`,{headers:{'X-CSRFToken':(await context.cookies(base)).find(c=>c.name==='csrftoken')?.value||''},data:{...latest,active:false}});
  }
  await browser.close();
}
