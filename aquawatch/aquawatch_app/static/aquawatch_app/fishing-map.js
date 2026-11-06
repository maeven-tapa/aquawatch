import {loadMapLibrary, addBaseMap, element, reference} from './map-utils.js';
import {mountTripPlanner} from './trip-planner.js';

const data=JSON.parse(document.getElementById('fishing-data').textContent);
const config=JSON.parse(document.getElementById('map-config').textContent);
const panel=document.getElementById('habitat-panel'), content=document.getElementById('habitat-content');
const trip=document.getElementById('trip-content'), monitoring=document.getElementById('monitoring-details');
const feedback=document.getElementById('map-feedback');
const shapes=new Map(); let map, maps, bounds, selectedId, userMarker, tripFor;

function showTab(name) {
  content.hidden=name!=='habitat'; trip.hidden=name!=='trip';
  for(const tab of ['habitat','trip']) {
    const button=document.getElementById(`${tab}-tab`);
    button.setAttribute('aria-selected',String(tab===name));
    button.classList.toggle('button-secondary',tab!==name);
    button.tabIndex=tab===name?0:-1;
  }
  if(name==='trip' && tripFor!==selectedId) {
    tripFor=selectedId; mountTripPlanner(trip,data.zones.find(zone=>zone.id===selectedId));
  }
}
function selectZone(zone, scroll=true) {
  selectedId=zone.id; tripFor=null; monitoring.hidden=true;
  document.getElementById('habitat-title').textContent=zone.title;
  content.replaceChildren(element('p',`Reference pin: ${zone.center.lat.toFixed(6)}, ${zone.center.lng.toFixed(6)} · Draft habitat outline`,'muted'));
  content.append(element('p',`Area: ${(zone.area_square_meters/10000).toFixed(2)} hectares (${(zone.area_square_meters/1e6).toFixed(3)} km²)`));
  if(document.getElementById('zone-editor')) {
    const edit=element('button','Edit location, size and shape','button');
    edit.type='button';edit.addEventListener('click',()=>window.dispatchEvent(new CustomEvent('edit-fishing-zone',{detail:zone})));
    content.append(edit);
  }
  const cards=element('div',undefined,'habitat-fish-grid');
  for(const fish of data.fish) {
    const card=element('article',undefined,'habitat-fish-card');
    card.append(element('h3',fish.localName),element('p',fish.identification,'muted'),element('h4','Habitat'),element('p',fish.habitat));
    if(fish.note) card.append(element('p',fish.note,'muted'));
    card.append(reference(fish.source));
    if(fish.id==='sardines') card.append(reference(data.sources.salinas));
    cards.append(card);
  }
  content.append(cards,element('h3','Municipal-water and catch references'),element('p','These sketches are not official municipal limits or surveyed habitats. Julugan has a recorded fish sanctuary; confirm current restrictions and fishing access with the LGU.','muted'));
  for(const source of [...data.sources.waters,...data.sources.catches]) content.append(reference(source));
  for(const choice of document.querySelectorAll('[data-zone-id]')) choice.setAttribute('aria-pressed',String(choice.dataset.zoneId===zone.id));
  for(const [id,polygon] of shapes) {polygon.setStyle({fillColor:id===zone.id?'#ff8a3d':'#00a897',color:id===zone.id?'#ff8a3d':'#008f83',fillOpacity:id===zone.id ? .27 : .16,weight:id===zone.id?4:2});if(id===zone.id) polygon.bringToFront();}
  panel.hidden=false; showTab('habitat');
  if(scroll) panel.scrollIntoView({behavior:'smooth',block:'start'});
}
for(const choice of document.querySelectorAll('[data-zone-id]')) choice.addEventListener('click',()=>selectZone(data.zones.find(zone=>zone.id===choice.dataset.zoneId)));
document.getElementById('close-habitat').addEventListener('click',()=>{panel.hidden=true;document.querySelector(`[data-zone-id="${selectedId}"]`)?.focus();});
for(const name of ['habitat','trip']) document.getElementById(`${name}-tab`).addEventListener('click',()=>showTab(name));
document.querySelector('.habitat-tabs').addEventListener('keydown',event=>{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
  event.preventDefault();
  const name=event.key==='Home'?'habitat':event.key==='End'?'trip':content.hidden?'habitat':'trip';
  showTab(name); document.getElementById(`${name}-tab`).focus();
});
document.getElementById('close-details').addEventListener('click',()=>monitoring.hidden=true);
document.getElementById('show-fishing-zone').addEventListener('click',()=>{
  monitoring.hidden=true;
  if(map && bounds?.isValid()) map.fitBounds(bounds,{padding:[45,45]});
  else document.getElementById('habitat-catalog-title').scrollIntoView({behavior:'smooth'});
});
document.getElementById('show-monitoring-area').addEventListener('click',()=>{
  monitoring.hidden=false;
  if(map) map.setView([config.area.lat,config.area.lng],10);
});

async function startMap() {
  try {
    maps=await loadMapLibrary();
    map=maps.map('map',{zoomControl:false,scrollWheelZoom:false}).setView([(data.zones[0]?.center.lat ?? 14.41),(data.zones[0]?.center.lng ?? 120.77)],12);
    addBaseMap(maps,map);
    const monitoringCircle=maps.circle([config.area.lat,config.area.lng],{radius:20000,fillColor:'#00a8b5',fillOpacity:.08,color:'#00a8b5',opacity:.6,weight:2}).addTo(map);
    const monitoringMarker=maps.circleMarker([config.area.lat,config.area.lng],{radius:8,color:'#fff',fillColor:'#4285f4',fillOpacity:1,weight:2}).addTo(map);
    monitoringMarker.bindTooltip(element('span',config.area.label));
    monitoringMarker.on('click',()=>{monitoring.hidden=false;map.fitBounds(monitoringCircle.getBounds(),{padding:[45,45]});});
    map.on('click',()=>monitoring.hidden=true);
    bounds=maps.latLngBounds([]);
    const fishSvg='<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48"><circle cx="24" cy="24" r="21" fill="#ff5d3b" stroke="white" stroke-width="2"/><ellipse cx="21" cy="24" rx="11" ry="7" fill="white"/><path d="M29 24L39 16V32Z" fill="white"/><circle cx="16" cy="22" r="1.6" fill="#ff5d3b"/></svg>';
    for(const zone of data.zones) {
      const polygon=maps.polygon(zone.boundary.map(point=>[point.lat,point.lng]),{fillColor:'#00a897',fillOpacity:.16,color:'#008f83',weight:2}).addTo(map);
      shapes.set(zone.id,polygon);
      const marker=maps.marker([zone.center.lat,zone.center.lng],{title:zone.title,icon:maps.divIcon({html:fishSvg,className:'fish-map-marker',iconSize:[38,38],iconAnchor:[19,19]})}).addTo(map);
      polygon.on('click',()=>selectZone(zone)); marker.on('click',()=>selectZone(zone));
      zone.boundary.forEach(point=>bounds.extend([point.lat,point.lng]));
    }
    if(bounds.isValid()) map.fitBounds(bounds,{padding:[45,45]});
    const resize=new ResizeObserver(()=>map.invalidateSize({pan:false}));resize.observe(document.getElementById('map'));
  } catch(error) {
    feedback.textContent=error.message;feedback.hidden=false;
    const fallback=element('div','Interactive map unavailable. Choose an area below to open its habitat and trip-planning guide.','map-unavailable');
    document.getElementById('map').replaceChildren(fallback);
  }
}
document.getElementById('show-my-location')?.addEventListener('click',()=>{
  const status=document.getElementById('location-status');
  if(!map || !maps) {status.textContent='The map must be available before centering your location.';return;}
  if(!navigator.geolocation) {status.textContent='Location is not supported by this browser.';return;}
  monitoring.hidden=true;status.textContent='Finding current location…';
  navigator.geolocation.getCurrentPosition(position=>{
    const point={lat:position.coords.latitude,lng:position.coords.longitude};
    if(userMarker) userMarker.remove();
    userMarker=maps.circleMarker([point.lat,point.lng],{radius:9,color:'#fff',fillColor:'#4285f4',fillOpacity:1,weight:3}).addTo(map);
    map.setView([point.lat,point.lng],15);status.textContent=`${point.lat.toFixed(5)}, ${point.lng.toFixed(5)}`;
  },error=>status.textContent=error.code===1?'Location permission denied':'Location unavailable. Turn on GPS and try again.',{enableHighAccuracy:true,timeout:10000,maximumAge:30000});
});
startMap();
