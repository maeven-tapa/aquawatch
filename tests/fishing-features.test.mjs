import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {HOUR, dateKey, dayStart, candidateWindow, tideTurns, parseForecast} from '../aquawatch/aquawatch_app/static/aquawatch_app/fishing-forecast.js';

const time=(hour,minute=0)=>Date.parse(`2026-11-06T${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}:00+08:00`);
const fixture=(levels=Array.from({length:24},(_,i)=>i/10))=>({hours:levels.map((level,i)=>({time:time(i),seaLevel:level,waveHeight:.3,windSpeed:2,weatherCode:0})),daylight:[{sunrise:time(6),sunset:time(18)}],fetchedAt:time(6)});

test('monthly zones and 175 labeled afternoon samples match the updated catalog',()=>{
  const data=JSON.parse(readFileSync(new URL('../aquawatch/aquawatch_app/static/aquawatch_app/fishing-data.json',import.meta.url),'utf8'));
  assert.equal(data.zones.length,10);assert.equal(data.fish.length,6);assert.equal(data.sampleHistory.length,175);
  assert.deepEqual(data.months.map(month=>month.month),Array.from({length:12},(_,i)=>`2026-${String(i+1).padStart(2,'0')}`));
  assert.deepEqual(data.months.map(month=>month.zones.length),[14,11,18,13,20,16,12,17,15,16,10,13]);
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
