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
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxZoom:19,keepBuffer:1,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);
  L.control.zoom({position:'bottomleft'}).addTo(map);
}
