import {loadMapLibrary,addBaseMap} from './map-utils.js';
import {starterBoundary,boundaryCenter,addFishingEnvelope} from './zone-shape-tools.js';

const boundary=document.getElementById('id_boundary'), latitude=document.getElementById('id_latitude'), longitude=document.getElementById('id_longitude');
const status=document.getElementById('admin-zone-status');
let L,map,layers=[];
const read=()=>{
  const points=JSON.parse(boundary.value || '[]') ?? [];
  if(!Array.isArray(points) || points.some(p=>!Number.isFinite(p?.lat)||!Number.isFinite(p?.lng))) throw Error('Each boundary point needs numeric lat and lng.');
  return points;
};
function redraw() {
  try {
    const points=read();
    status.textContent='';
    if(!map)return;
    layers.forEach(layer=>layer.remove());layers=[];
    if(points.length>=3)layers.push(L.polygon(points.map(p=>[p.lat,p.lng]),{color:'#008f83',weight:3}).addTo(map));
    points.forEach((p,i)=>{
      const marker=L.marker([p.lat,p.lng],{draggable:true,title:`Boundary point ${i+1}`,icon:L.divIcon({className:'zone-vertex-marker',html:`${i+1}`,iconSize:[28,28],iconAnchor:[14,14]})}).addTo(map);
      marker.on('dragend',()=>{const next=marker.getLatLng();points[i]={lat:next.lat,lng:next.lng};boundary.value=JSON.stringify(points,null,2);redraw();});
      marker.on('contextmenu',()=>{points.splice(i,1);boundary.value=JSON.stringify(points,null,2);redraw();});
      layers.push(marker);
    });
    if(latitude.value.trim() && longitude.value.trim() && Number.isFinite(Number(latitude.value)) && Number.isFinite(Number(longitude.value))) {
      const marker=L.marker([Number(latitude.value),Number(longitude.value)],{draggable:true,title:'Zone center pin',icon:L.divIcon({className:'zone-center-marker',html:'',iconSize:[22,22],iconAnchor:[11,11]})}).addTo(map);
      marker.on('dragend',()=>{latitude.value=marker.getLatLng().lat;longitude.value=marker.getLatLng().lng;});
      layers.push(marker);
    }
  } catch(error) {status.textContent=error.message;}
}
function centerPin() {const p=boundaryCenter(read());latitude.value=p.lat;longitude.value=p.lng;}
document.getElementById('admin-zone-starter').addEventListener('click',()=>{
  boundary.value=JSON.stringify(starterBoundary,null,2);centerPin();redraw();
  map?.fitBounds(starterBoundary.map(p=>[p.lat,p.lng]),{padding:[45,45],animate:false});
});
document.getElementById('admin-zone-center').addEventListener('click',()=>{try{centerPin();redraw();}catch(error){status.textContent=error.message;}});
document.getElementById('admin-zone-clear').addEventListener('click',()=>{boundary.value='[]';redraw();});
for(const field of [boundary,latitude,longitude])field.addEventListener('change',redraw);
async function start() {
  try {
    L=await loadMapLibrary();map=L.map('admin-zone-map',{scrollWheelZoom:false}).setView([14.41,120.78],12);addBaseMap(L,map);
    const envelope=JSON.parse(document.getElementById('zone-envelope').textContent);
    addFishingEnvelope(L,map,envelope);
    const bounds=L.latLngBounds(envelope.map(p=>[p.lat,p.lng]));
    try{read().forEach(p=>bounds.extend([p.lat,p.lng]));}catch{/* Keep malformed input available for correction. */}
    map.fitBounds(bounds,{padding:[20,20]});
    map.on('click',e=>{try{const points=read();points.push({lat:e.latlng.lat,lng:e.latlng.lng});boundary.value=JSON.stringify(points,null,2);redraw();}catch(error){status.textContent=error.message;}});
    redraw();
  } catch(error) {status.textContent=`Map unavailable. Edit the coordinate fields below. ${error.message}`;}
}
start();
