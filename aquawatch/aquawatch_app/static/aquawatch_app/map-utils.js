let mapsPromise;
export function loadMapLibrary() {
  if (globalThis.L?.map) return Promise.resolve(globalThis.L);
  if (mapsPromise) return mapsPromise;
  mapsPromise = new Promise((resolve, reject) => {
    const css = document.createElement('link');css.rel='stylesheet';
    css.href=new URL('./vendor/leaflet/leaflet.css',import.meta.url).href;document.head.append(css);
    const script = document.createElement('script');
    const timer = setTimeout(() => reject(new Error('The map could not load. Use the area list and coordinates below.')), 15000);
    script.onload = () => {clearTimeout(timer); resolve(globalThis.L);};
    script.onerror = () => {clearTimeout(timer); reject(new Error('Map connection unavailable. Use the area list and coordinates below.'));};
    script.src = new URL('./vendor/leaflet/leaflet.js',import.meta.url).href;
    script.async = true;
    document.head.append(script);
  });
  return mapsPromise;
}

export function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
export function reference(source) {
  const link = element('a', source.title, 'habitat-source');
  if (source.url.startsWith('https://')) link.href = source.url;
  link.target = '_blank'; link.rel = 'noopener noreferrer';
  return link;
}
export function addBaseMap(L,map) {
  const notice=L.control({position:'bottomleft'});
  let status,failed=false;
  notice.onAdd=()=>{
    status=L.DomUtil.create('div','map-tile-status');
    status.hidden=true;status.setAttribute('role','status');
    status.textContent='Basemap unavailable. Zone outlines and GPS points are still shown. Try refreshing later.';
    L.DomEvent.disableClickPropagation(status);
    return status;
  };
  notice.addTo(map);
  const layer=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxZoom:19,keepBuffer:1,updateWhenIdle:true,
    // Identify the actual requesting site; never spoof Referer or proxy tiles.
    referrerPolicy:'strict-origin-when-cross-origin',
    errorTileUrl:'data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"></svg>'),
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  });
  layer.on('loading',()=>{failed=false;status.hidden=true;});
  layer.on('tileerror',()=>{failed=true;status.hidden=false;});
  layer.on('load',()=>{status.hidden=!failed;});
  layer.addTo(map);
  if(!map.zoomControl)L.control.zoom({position:'bottomleft'}).addTo(map);
  return layer;
}
