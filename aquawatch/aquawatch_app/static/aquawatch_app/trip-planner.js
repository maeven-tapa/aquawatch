import {dateKey, dayStart, HOUR, TIME_ZONE, fetchForecast, tideTurns, candidateWindow} from './fishing-forecast.js';
import {element, reference} from './map-utils.js';
const active = new WeakMap();
const clock = time => new Intl.DateTimeFormat('en', {timeZone:TIME_ZONE, hour:'numeric', minute:'2-digit', hour12:true}).format(time);
const date = time => new Intl.DateTimeFormat('en', {timeZone:TIME_ZONE, weekday:'short', month:'short', day:'numeric'}).format(time);

export function mountTripPlanner(container, zone) {
  const token = Symbol(); active.set(container, token);
  container.replaceChildren();
  const form = element('div', undefined, 'trip-controls');
  const day = element('select'), phase = element('select'), travel = element('input');
  day.id='trip-day'; phase.id='trip-phase'; travel.id='trip-travel';
  for (let i=0; i<3; i++) {
    const time=dayStart(Date.now())+i*24*HOUR, option=element('option', `${['Today','Tomorrow','+2 days'][i]} · ${date(time)}`);
    option.value=dateKey(time); day.append(option);
  }
  for (const [value,label] of [['rising','Rising tide'],['falling','Falling tide']]) {
    const option=element('option',label); option.value=value; phase.append(option);
  }
  travel.type='number'; travel.min='15'; travel.max='180'; travel.step='15'; travel.value='30';
  for (const [labelText,control] of [['Fishing date',day],['Tide preference',phase],['One-way travel estimate (minutes)',travel]]) {
    const label=element('label',labelText); label.htmlFor=control.id; label.append(control); form.append(label);
  }
  const result=element('div', undefined, 'trip-result'); result.setAttribute('role','status'); result.setAttribute('aria-live','polite');
  const refresh=element('button','Refresh forecast','button button-secondary'); refresh.type='button';
  container.append(element('h3','Fishing efficiency & trip timing'), element('p','Plan a daylight departure using tide estimates and your travel time. All times are Manila time.','muted'), form,result,refresh);
  const details=element('details', undefined, 'trip-guidance'); details.append(element('summary','High or low tide? Guidance & sources'));
  details.append(element('p','In shallow water, rising tide may bring fish into shallows; falling tide may move fish toward deeper water. Neither high nor low tide is always best. Species, gear and local conditions matter.'));
  details.append(element('p','The candidate is the first matching two-hour daylight period, with complete outbound-travel and fishing forecasts: wind below 7 m/s, waves below 1 m, and no forecast fog, heavy rain or thunderstorm. These are app defaults, not vessel-specific safety limits. A return trip is not planned.'));
  details.append(element('p','Hourly sea-level estimates use an approximately 8 km model grid and include tides and other sea-level effects. MSL means mean sea level, not actual depth. Coastal accuracy is limited; these are not official tide predictions or navigation guidance.'));
  for (const [title,url] of [
    ['NAMRIA — official tide predictions','https://www.namria.gov.ph/'],
    ['PAGASA — gale warnings','https://www.pagasa.dost.gov.ph/marine/gale-warning'],
    ['Open-Meteo — forecast data & limitations','https://open-meteo.com/en/docs/marine-weather-api'],
    ['FWC — general saltwater tide guidance','https://myfwc.com/fishing/saltwater/outreach/how-to-fish/']]) details.append(reference({title,url}));
  container.append(element('p','Planning estimate only, not a catch forecast or clearance to sail. Check NAMRIA, PAGASA and local PCG advice before leaving.','planning-note'),details);
  let forecast=null;
  function update() {
    if (!forecast) return;
    result.replaceChildren(element('p',`Open-Meteo model · Updated ${date(forecast.fetchedAt)} ${clock(forecast.fetchedAt)}`,'muted'));
    const turns=tideTurns(forecast.hours).filter(turn=>dateKey(turn.time)===day.value);
    for (const turn of turns) result.append(element('p',`${turn.high?'High water':'Low water'} ≈ ${clock(turn.time)} · ${turn.height.toFixed(2)} m MSL`));
    if (!turns.length) result.append(element('p','High/low-water estimates unavailable for this date.'));
    if (!travel.checkValidity() || !travel.value) {result.append(element('p','Enter a travel estimate from 15 to 180 minutes, in steps of 15.')); return;}
    const window=candidateWindow(forecast,day.value,Date.now(),Number(travel.value),phase.value);
    if (window) {
      result.append(element('h4',`Candidate departure: ${clock(window.departure)}`));
      result.append(element('p',`At the area: ${clock(window.arrival)}–${clock(window.end)} · ${phase.value} tide`));
      result.append(element('p',`Forecast: wind up to ${window.maxWind.toFixed(1)} m/s · waves up to ${window.maxWaves.toFixed(1)} m`));
    } else result.append(element('p','No matching daylight window passes the planning filters. Try another date or tide phase, or refresh the data.'));
  }
  async function load(force=false) {
    refresh.disabled=true; result.replaceChildren(element('p','Checking tide, daylight and marine forecasts…'));
    try {
      const data=await fetchForecast(zone,force);
      if (active.get(container)!==token) return;
      forecast=data; update();
    } catch (_) {
      if (active.get(container)===token) {forecast=null;result.replaceChildren(element('p',"Forecast unavailable. No departure time can be suggested. Check NAMRIA's official tide predictions."));}
    } finally {if(active.get(container)===token) refresh.disabled=false;}
  }
  for (const control of [day,phase,travel]) control.addEventListener('change',update);
  refresh.addEventListener('click',()=>load(true));
  load();
  // Re-evaluate past departures while the panel remains open. Stop when replaced.
  const timer=setInterval(()=>{
    if(active.get(container)!==token || !container.isConnected) clearInterval(timer); else update();
  },60000);
}
