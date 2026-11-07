export const starterBoundary = [
  {lat:14.407,lng:120.777},{lat:14.407,lng:120.783},
  {lat:14.413,lng:120.783},{lat:14.413,lng:120.777}
];

// Choose the midpoint of an interior scanline segment, including for concave shapes.
export function boundaryCenter(points) {
  if (!Array.isArray(points) || points.length < 3 || points.some(p => !Number.isFinite(p?.lat) || !Number.isFinite(p?.lng))) {
    throw Error('Enter at least three valid boundary points first.');
  }
  const levels = [...new Set(points.map(p => p.lat))].sort((a,b) => a-b);
  let best;
  for (let level=1; level<levels.length; level++) {
    const lat=(levels[level-1]+levels[level])/2, intersections=[];
    points.forEach((a,i) => {
      const b=points[(i+1)%points.length];
      if ((a.lat>lat)!==(b.lat>lat)) intersections.push(a.lng+(b.lng-a.lng)*(lat-a.lat)/(b.lat-a.lat));
    });
    intersections.sort((a,b)=>a-b);
    for (let i=0; i+1<intersections.length; i+=2) {
      const width=intersections[i+1]-intersections[i];
      if (width>0 && (!best || width>best.width)) best={lat,lng:(intersections[i]+intersections[i+1])/2,width};
    }
  }
  if (!best) throw Error('The boundary needs a nonzero area before centering the pin.');
  return {lat:best.lat,lng:best.lng};
}

export function addFishingEnvelope(L,map,points) {
  return L.polygon(points.map(p=>[p.lat,p.lng]),{color:'#737373',dashArray:'8 6',fillOpacity:.04,weight:2,interactive:false}).addTo(map);
}
