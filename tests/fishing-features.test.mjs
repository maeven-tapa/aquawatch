import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {HOUR, dateKey, dayStart, candidateWindow, tideTurns, parseForecast} from '../aquawatch/aquawatch_app/static/aquawatch_app/fishing-forecast.js';
import {zoneDateLabel,publicationLabel,recurrenceLabel} from '../aquawatch/aquawatch_app/static/aquawatch_app/zone-details.js';
import {boundaryCenter,starterBoundary} from '../aquawatch/aquawatch_app/static/aquawatch_app/zone-shape-tools.js';

const time=(hour,minute=0)=>Date.parse(`2026-11-06T${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}:00+08:00`);
const fixture=(levels=Array.from({length:24},(_,i)=>i/10))=>({hours:levels.map((level,i)=>({time:time(i),seaLevel:level,waveHeight:.3,windSpeed:2,weatherCode:0})),daylight:[{sunrise:time(6),sunset:time(18)}],fetchedAt:time(6)});

test('zone details preserve the exact date and show publication in Philippine time',()=>{
  assert.equal(zoneDateLabel('2027-01-17'),'January 17, 2027');
  assert.equal(publicationLabel({active:false,published_at:null}),'Unpublished');
  assert.match(publicationLabel({active:true,published_at:null}),/unavailable/);
  const published=publicationLabel({active:true,published_at:'2026-11-07T18:30:00Z'});
  assert.match(published,/November 8, 2026/);
  assert.match(published,/2:30/);
  assert.match(recurrenceLabel({date:'2026-11-17',repeats_annually:true}),/Original zone date: November 17, 2026/);
  assert.equal(recurrenceLabel({repeats_annually:false}),'Applies to this year only');
});

test('center repair finds an interior point for a concave boundary',()=>{
  const points=[{lat:0,lng:0},{lat:0,lng:4},{lat:1,lng:4},{lat:1,lng:1},{lat:4,lng:1},{lat:4,lng:0}];
  const center=boundaryCenter(points);
  assert.ok(center.lng>0 && center.lat>0 && (center.lat<1 || center.lng<1));
  const starter=boundaryCenter(starterBoundary);
  assert.ok(starter.lat>14.407 && starter.lat<14.413 && starter.lng>120.777 && starter.lng<120.783);
  assert.throws(()=>boundaryCenter([]));
  assert.throws(()=>boundaryCenter([{lat:1,lng:0},{lat:1,lng:1},{lat:1,lng:2}]));
});

test('monthly zones and 175 labeled afternoon samples match the updated catalog',()=>{
  const data=JSON.parse(readFileSync(new URL('../aquawatch/aquawatch_app/static/aquawatch_app/fishing-data.json',import.meta.url),'utf8'));
  assert.equal(data.zones.length,10);assert.equal(data.fish.length,6);assert.equal(data.sampleHistory.length,175);
  assert.deepEqual(data.months.map(month=>month.month),Array.from({length:12},(_,i)=>`2026-${String(i+1).padStart(2,'0')}`));
  assert.deepEqual(data.months.map(month=>month.zones.length),[14,11,18,13,20,16,12,17,15,16,10,13]);
  assert.equal(new Set(data.months.flatMap(month=>month.zones.map(z=>z.id))).size,175);
  const counts=new Map();
  for(const row of data.sampleHistory) {
    const key=dateKey(row.receivedAt);counts.set(key,(counts.get(key)||0)+1);
    const local=new Date(row.receivedAt+8*HOUR),minutes=local.getUTCHours()*60+local.getUTCMinutes();
    assert.ok(minutes>720 && minutes<=1200);assert.equal(row.isSample,true);assert.equal(row.isDistress,false);assert.equal(row.alertType,'');
  }
  assert.deepEqual([...counts.keys()],Array.from({length:28},(_,i)=>i+1).filter(day=>day<15||day>17).map(day=>`2026-10-${String(day).padStart(2,'0')}`));
  assert.ok([...counts.values()].every(n=>n===7));
  assert.equal(new Set(data.sampleHistory.map(row=>row.receivedAt)).size,175);
  for(const zone of data.months.flatMap(month=>month.zones)) {assert.ok(zone.boundary.length>=3&&zone.boundary.length<=100);assert.equal(zone.proposed,true);}
});
test('departure stays in daylight, is future, and accounts for travel',()=>{
  assert.deepEqual(candidateWindow(fixture(),dateKey(time(6)),time(6),30,'rising'),{departure:time(6,30),arrival:time(7),end:time(9),maxWind:2,maxWaves:.3});
  assert.equal(candidateWindow(fixture(),dateKey(time(6)),time(6),30,'falling'),null);
  const data=fixture();data.fetchedAt=time(9,45);
  assert.equal(candidateWindow(data,dateKey(time(9)),time(9,45),30,'rising').departure,time(10,30));
});
test('hazard filtering includes outbound travel and rejects missing or stale conditions',()=>{
  const data=fixture();data.hours[6].weatherCode=95;
  assert.equal(candidateWindow(data,dateKey(time(6)),time(6),30,'rising').departure,time(7,30));
  for(const change of [{waveHeight:null},{waveHeight:1},{windSpeed:7},{weatherCode:45},{weatherCode:65},{seaLevel:null}]) {
    const invalid=fixture();invalid.hours=invalid.hours.map(hour=>({...hour,...change}));
    assert.equal(candidateWindow(invalid,dateKey(time(6)),time(6),30,'rising'),null);
  }
  const stale=fixture();stale.fetchedAt=time(1);
  assert.equal(candidateWindow(stale,dateKey(time(6)),time(6),30,'rising'),null);
  assert.equal(candidateWindow(fixture(),dateKey(time(6)),time(6),-1,'rising'),null);
});
test('turn detection handles flat peaks and never bridges missing data',()=>{
  assert.deepEqual(tideTurns(fixture([0,.5,1,1,.5,0,.5]).hours),[{time:time(2,30),height:1,high:true},{time:time(5),height:0,high:false}]);
  assert.deepEqual(tideTurns(fixture([0,null,1,null,0]).hours),[]);
  assert.equal(dateKey(time(0)),'2026-11-06');assert.equal(dayStart(time(20)),time(0));
});
test('forecast parsing joins weather by timestamp without converting nulls into zero',()=>{
  const parsed=parseForecast({hourly:{time:[1000,4600,8200],sea_level_height_msl:[.2,null,.7],wave_height:[.3,.4,.5]}},
    {hourly:{time:[8200,1000],wind_speed_10m:[4,2],weather_code:[95,0]},daily:{sunrise:[1000],sunset:[20000]}},9000);
  assert.equal(parsed.hours[0].windSpeed,2);assert.equal(parsed.hours[1].seaLevel,null);assert.equal(parsed.hours[1].windSpeed,null);assert.equal(parsed.hours[2].weatherCode,95);
});
