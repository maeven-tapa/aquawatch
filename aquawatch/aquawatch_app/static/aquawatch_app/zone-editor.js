import {loadMapLibrary,addBaseMap} from './map-utils.js';
const editor=document.getElementById('zone-editor'), form=document.getElementById('zone-form');
const field=id=>document.getElementById(`zone-${id}`);
let current=null, map, L, polygon, centerMarker, handles=[];
const boundary=()=>{const p=JSON.parse(field('boundary').value);if(!Array.isArray(p))throw Error('Use a JSON array of vertices.');return p;};
const center=()=>({lat:Number(field('lat').value),lng:Number(field('lng').value)});
function redraw() {
  try {
    const points=boundary(), c=center();
    if(points.some(p=>!Number.isFinite(p.lat)||!Number.isFinite(p.lng)))throw Error('Each vertex needs numeric lat and lng.');
    const sx=111320*Math.cos(c.lat*Math.PI/180), origin=points[0];
    let area=0;
    if(origin)points.forEach((p,i)=>{const q=points[(i+1)%points.length];area+=(p.lng-origin.lng)*sx*(q.lat-origin.lat)*111320-(q.lng-origin.lng)*sx*(p.lat-origin.lat)*111320;});
    field('area').textContent=`Area: ${(Math.abs(area)/20000).toFixed(2)} hectares (${(Math.abs(area)/2e6).toFixed(3)} km²)`;
    if(!map)return;
    polygon?.remove();handles.forEach(m=>m.remove());handles=[];centerMarker?.remove();
    if(points.length>=3)polygon=L.polygon(points.map(p=>[p.lat,p.lng]),{color:'#008f83',weight:3}).addTo(map);
    points.forEach((p,i)=>{
      const m=L.marker([p.lat,p.lng],{draggable:true,title:`Boundary point ${i+1}`,icon:L.divIcon({className:'zone-vertex-marker',html:`<span>${i+1}</span>`,iconSize:[28,28],iconAnchor:[14,14]})}).addTo(map);
      m.on('dragend',()=>{points[i]={lat:m.getLatLng().lat,lng:m.getLatLng().lng};field('boundary').value=JSON.stringify(points,null,2);redraw();});
      m.on('contextmenu',()=>{points.splice(i,1);field('boundary').value=JSON.stringify(points,null,2);redraw();});handles.push(m);
    });
    centerMarker=L.marker([c.lat,c.lng],{draggable:true,title:'Move the entire zone',icon:L.divIcon({className:'zone-center-marker',html:'<span></span>',iconSize:[22,22],iconAnchor:[11,11]})}).addTo(map);
    centerMarker.on('dragend',()=>{
      const next=centerMarker.getLatLng(),lat=next.lat-c.lat,lng=next.lng-c.lng;
      field('lat').value=next.lat;field('lng').value=next.lng;
      field('boundary').value=JSON.stringify(points.map(p=>({lat:p.lat+lat,lng:p.lng+lng})),null,2);redraw();
    });
    field('save-status').textContent='';
  } catch(error){field('save-status').textContent=error.message;}
}
async function open(zone) {
  current=zone;editor.hidden=false;
  field('name').value=zone?.title||'New Amaya fishing zone';
  field('month').value=zone?.month||field('month').defaultValue;
  field('lat').value=zone?.center.lat??14.41;field('lng').value=zone?.center.lng??120.78;
  field('active').checked=zone?.active??true;field('scale').value=100;
  field('boundary').value=JSON.stringify(zone?.boundary||[{lat:14.407,lng:120.777},{lat:14.407,lng:120.783},{lat:14.413,lng:120.783},{lat:14.413,lng:120.777}],null,2);
  editor.scrollIntoView({behavior:'smooth'});
  if(!map)try {
    L=await loadMapLibrary();map=L.map('zone-edit-map',{scrollWheelZoom:false}).setView([14.41,120.78],13);addBaseMap(L,map);
    map.on('click',e=>{try{const points=boundary();points.push({lat:e.latlng.lat,lng:e.latlng.lng});field('boundary').value=JSON.stringify(points,null,2);redraw();}catch(error){field('save-status').textContent=error.message;}});
  } catch(error){field('save-status').textContent=`Map unavailable. You can edit coordinates below. ${error.message}`;}
  redraw();if(map){map.invalidateSize();if(polygon)map.fitBounds(polygon.getBounds(),{padding:[35,35]});}
}
window.addEventListener('edit-fishing-zone',e=>open(e.detail));
document.getElementById('new-fishing-zone').addEventListener('click',()=>open(null));
document.getElementById('close-zone-editor').addEventListener('click',()=>editor.hidden=true);
document.getElementById('clear-zone-points').addEventListener('click',()=>{field('boundary').value='[]';redraw();});
for(const id of ['boundary','lat','lng'])field(id).addEventListener('change',redraw);
document.getElementById('resize-zone').addEventListener('click',()=>{
  try{const ratio=Number(field('scale').value)/100;if(!Number.isFinite(ratio)||ratio<.1||ratio>3)throw Error('Choose a size from 10% to 300%.');const c=center();field('boundary').value=JSON.stringify(boundary().map(p=>({lat:c.lat+(p.lat-c.lat)*ratio,lng:c.lng+(p.lng-c.lng)*ratio})),null,2);field('scale').value=100;redraw();if(map&&polygon)map.fitBounds(polygon.getBounds(),{padding:[35,35]});}catch(error){field('save-status').textContent=error.message;}
});
form.addEventListener('submit',async e=>{
  e.preventDefault();const button=document.getElementById('save-zone');button.disabled=true;
  try{
    const month=field('month').value;
    const response=await fetch(`/fishing-zones/${current?`${current.id}/`:''}`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({title:field('name').value,month,center:center(),boundary:boundary(),active:field('active').checked,...(current?{version:current.version}:{})})});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Unable to save zone.');
    window.location.assign(`/map/?month=${encodeURIComponent(month)}`);
  }catch(error){field('save-status').textContent=error.message;}finally{button.disabled=false;}
});
