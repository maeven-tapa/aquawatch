// Same planning rules as Android's FishingTripPlan.kt. No measured catch score
// or navigation clearance is inferred from these coarse forecast values.
export const HOUR = 3600000;
export const TIME_ZONE = 'Asia/Manila';
const forecastCache = new Map();

export function dateKey(time) {
  const parts = new Intl.DateTimeFormat('en', {timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit'}).formatToParts(new Date(time));
  const value = name => parts.find(part => part.type === name).value;
  return `${value('year')}-${value('month')}-${value('day')}`;
}
export const dayStart = time => Date.parse(`${dateKey(time)}T00:00:00+08:00`);
const finite = value => typeof value === 'number' && Number.isFinite(value) ? value : null;

export function parseForecast(marine, weather, fetchedAt) {
  const mh = marine.hourly, wh = weather.hourly;
  if (!Array.isArray(mh?.time) || !Array.isArray(wh?.time)) throw new Error('Forecast unavailable');
  const weatherIndices = new Map(wh.time.map((time, i) => [time, i]));
  const hours = mh.time.filter(time => Number.isFinite(time) && time > 0).map(seconds => {
    const i = mh.time.indexOf(seconds), wi = weatherIndices.get(seconds);
    const wind = finite(wh.wind_speed_10m?.[wi]), waves = finite(mh.wave_height?.[i]);
    const code = finite(wh.weather_code?.[wi]);
    return {time: seconds * 1000, seaLevel: finite(mh.sea_level_height_msl?.[i]),
      waveHeight: waves !== null && waves >= 0 ? waves : null,
      windSpeed: wind !== null && wind >= 0 ? wind : null,
      weatherCode: code !== null && Number.isInteger(code) && code >= 0 && code <= 99 ? code : null};
  });
  const unique = [...new Map(hours.map(hour => [hour.time, hour])).values()].sort((a,b) => a.time - b.time);
  const daylight = (weather.daily?.sunrise || []).map((sunrise, i) => ({sunrise: sunrise * 1000, sunset: weather.daily.sunset?.[i] * 1000}))
    .filter(light => light.sunrise > 0 && light.sunset > light.sunrise && light.sunset - light.sunrise < 24 * HOUR);
  if (!unique.some(hour => hour.seaLevel !== null) || !daylight.length) throw new Error('No usable forecast');
  return {hours: unique, daylight, fetchedAt};
}

export function tideTurns(hours) {
  const turns = [];
  for (let i = 1; i < hours.length - 1;) {
    const current = hours[i], height = current.seaLevel;
    if (!Number.isFinite(height)) {i++; continue;}
    let end = i;
    while (end < hours.length - 1 && hours[end+1].time - hours[end].time === HOUR &&
      Number.isFinite(hours[end+1].seaLevel) && Math.abs(hours[end+1].seaLevel - height) < .000001) end++;
    const before = hours[i-1], after = hours[end+1];
    if (current.time - before.time === HOUR && after && after.time - hours[end].time === HOUR &&
      Number.isFinite(before.seaLevel) && Number.isFinite(after.seaLevel)) {
      const high = height > before.seaLevel && height > after.seaLevel;
      const low = height < before.seaLevel && height < after.seaLevel;
      if (high || low) turns.push({time: current.time + (hours[end].time - current.time) / 2, height, high});
    }
    i = end + 1;
  }
  return turns;
}

export function candidateWindow(forecast, day, now, travelMinutes, phase) {
  if (!Number.isInteger(travelMinutes) || travelMinutes < 15 || travelMinutes > 180 || !['rising','falling'].includes(phase)) return null;
  if (now - forecast.fetchedAt < 0 || now - forecast.fetchedAt > 3 * HOUR) return null;
  const daylight = forecast.daylight.find(light => dateKey(light.sunrise) === day);
  if (!daylight) return null;
  for (let i = 0; i < forecast.hours.length - 2; i++) {
    const window = forecast.hours.slice(i, i+3);
    if (window.some(hour => !Number.isFinite(hour.seaLevel)) || window[1].time-window[0].time !== HOUR || window[2].time-window[1].time !== HOUR) continue;
    const arrival = window[0].time, departure = arrival - travelMinutes * 60000, end = window[2].time;
    if (dateKey(arrival) !== day || departure < now || departure < daylight.sunrise || end > daylight.sunset) continue;
    const matching = window.slice(1).every((hour, index) => phase === 'rising' ? hour.seaLevel - window[index].seaLevel > .01 : hour.seaLevel - window[index].seaLevel < -.01);
    if (!matching) continue;
    const start = Math.floor(departure / HOUR) * HOUR;
    const conditions = forecast.hours.filter(hour => hour.time >= start && hour.time <= end);
    if (conditions.length !== (end-start) / HOUR + 1 || conditions.some((hour, j) => j && hour.time - conditions[j-1].time !== HOUR)) continue;
    if (conditions.some(hour => !Number.isFinite(hour.windSpeed) || hour.windSpeed < 0 || hour.windSpeed >= 7 ||
      !Number.isFinite(hour.waveHeight) || hour.waveHeight < 0 || hour.waveHeight >= 1 || !Number.isInteger(hour.weatherCode) ||
      hour.weatherCode < 0 || hour.weatherCode > 99 || hour.weatherCode >= 95 || [45,48,65,67,82].includes(hour.weatherCode))) continue;
    return {departure, arrival, end, maxWind: Math.max(...conditions.map(hour => hour.windSpeed)), maxWaves: Math.max(...conditions.map(hour => hour.waveHeight))};
  }
  return null;
}

export async function fetchForecast(zone, refresh = false) {
  const key = `${zone.center.lat},${zone.center.lng}`, cached = forecastCache.get(key);
  if (!refresh && cached && Date.now() - cached.fetchedAt >= 0 && Date.now() - cached.fetchedAt < 900000) return cached;
  const params = new URLSearchParams({latitude: zone.center.lat, longitude: zone.center.lng, timeformat: 'unixtime', timezone: TIME_ZONE, forecast_days: 3, past_days: 1});
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
  async function get(url) {
    const response = await fetch(url, {signal: controller.signal});
    if (!response.ok) throw new Error('Forecast service unavailable');
    const json = await response.json();
    if (json.error) throw new Error('Forecast service unavailable');
    return json;
  }
  try {
    const [marine, weather] = await Promise.all([
      get(`https://marine-api.open-meteo.com/v1/marine?${params}&hourly=sea_level_height_msl,wave_height&cell_selection=sea`),
      get(`https://api.open-meteo.com/v1/forecast?${params}&hourly=wind_speed_10m,weather_code&daily=sunrise,sunset&wind_speed_unit=ms`)
    ]);
    const result = parseForecast(marine, weather, Date.now());
    forecastCache.set(key, result);
    return result;
  } finally {clearTimeout(timer);}
}
