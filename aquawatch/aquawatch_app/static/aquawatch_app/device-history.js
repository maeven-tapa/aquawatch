import {loadMapLibrary, addBaseMap} from './map-utils.js';
const entries=JSON.parse(document.getElementById('status-history-data').textContent);
const config=JSON.parse(document.getElementById('history-map-config').textContent);
const selector=document.getElementById('history-entry');
if(selector) {
  const from=document.getElementById('history-from'), to=document.getElementById('history-to'), source=document.getElementById('history-source');
  const feedback=document.getElementById('history-map-feedback');
  let maps,map,marker,paths=[],filtered=entries;
  function selectedEntry() {return filtered.find(entry=>entry.id===selector.value) || filtered[0];}
  function updatePosition() {
    const entry=selectedEntry();
    if(!entry) {feedback.textContent='No entries match these filters.';if(marker) {marker.remove();marker=null;}return;}
    feedback.textContent=`${entry.receivedLabel} · ${entry.isSample?'Sample':'Device log'} · ${entry.latitude.toFixed(6)}, ${entry.longitude.toFixed(6)}`;
    if(map) {
      const point=[entry.latitude,entry.longitude];
      if(!marker) marker=maps.circleMarker(point,{radius:8,color:'#fff',weight:2,fillOpacity:1}).addTo(map);
      marker.setLatLng(point);marker.setStyle({fillColor:entry.isSample?'#ff8a3d':'#00a897'});map.panTo(point);
    }
  }
  function updatePaths() {
    if(!map) return;
    paths.forEach(path=>path.remove());paths=[];
    for(const sample of [true,false]) {
      const points=filtered.filter(entry=>entry.isSample===sample).slice().reverse().map(entry=>[entry.latitude,entry.longitude]);
      if(points.length>1) paths.push(maps.polyline(points,{color:sample?'#ff8a3d':'#00a897',weight:3}).addTo(map));
    }
  }
  function filter() {
    const previous=selector.value;
    filtered=entries.filter(entry=>(!from.value || entry.dateKey>=from.value) && (!to.value || entry.dateKey<=to.value) &&
      (source.value==='all' || entry.isSample===(source.value==='sample')));
    selector.replaceChildren();
    for(const entry of filtered) {const option=document.createElement('option');option.value=entry.id;option.textContent=`${entry.receivedLabel} · ${entry.isSample?'Sample':'Device log'}`;selector.append(option);}
    if(filtered.some(entry=>entry.id===previous)) selector.value=previous;
    selector.disabled=!filtered.length;
    document.getElementById('history-count').textContent=`${filtered.length} of ${entries.length} entries`;
    const visible=new Set(filtered.map(entry=>entry.id));
    for(const row of document.querySelectorAll('[data-entry-id]')) row.hidden=!visible.has(row.dataset.entryId);
    updatePaths();updatePosition();
  }
  for(const control of [from,to,source]) control.addEventListener('change',filter);
  document.getElementById('history-reset').addEventListener('click',()=>{from.value='';to.value='';source.value='all';filter();});
  selector.addEventListener('change',updatePosition);
  updatePosition();
  loadMapLibrary().then(api=>{
    maps=api;const entry=selectedEntry();
    map=maps.map('status-history-map',{zoomControl:false,scrollWheelZoom:false}).setView(entry?[entry.latitude,entry.longitude]:[14.39453,120.825889],13);
    addBaseMap(maps,map);
    updatePaths();updatePosition();
  }).catch(()=>{
    const note=document.createElement('p');note.textContent='Map unavailable. Exact coordinates remain available in the status selector and table.';note.className='map-unavailable';document.getElementById('status-history-map').replaceChildren(note);
  });
}
