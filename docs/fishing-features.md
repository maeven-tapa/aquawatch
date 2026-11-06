# Fishing features shared with Android

The map now offers the same 11 irregular Amaya-area polygons, fish markers, six
habitat profiles, and source links as Android. Select a marker, polygon, or area
button, then switch between habitat information and the trip-planning tab. The
area list and descriptions remain usable if a map cannot load. These two map
views bundle Leaflet 1.9.4 (BSD license included) and use attributed OpenStreetMap
tiles, so they do not depend on the existing Google Maps key. Browser caching
and referrers are left intact; there is no bulk/offline tile download. Automated
browser checks intercept tile requests instead of driving the public tile server.
The older monitoring-location settings picker retains its existing Google Maps
integration.

Trip planning covers today and the following two days in Asia/Manila time,
rising/falling modeled sea level, approximate high/low-water turns, adjustable
15–180 minute one-way travel, and a candidate two-hour daylight fishing window.
It uses the same Open-Meteo endpoints, missing-data handling, 15-minute memory
cache, three-hour freshness cutoff, and conservative weather filters as Android.
Official tide/weather links and forecast limitations are included. It does not
infer catch probability, navigation clearance, or municipal-water jurisdiction.

Device details show up to 500 actual received readings, a status selector, date
and source filters, a coordinate map, and separate sample/device-log paths. The
first existing device per account also displays 33 clearly labeled samples for
October 16–29, 2026 (two or three afternoon/evening records daily, ending at 8 PM).
These samples are a deterministic display overlay. They are not inserted into
DeviceReading, uploaded as real readings, or used for live status, alerts, or
trip recommendations. Real history is preserved and remains owner-scoped.

The JSON catalog is bundled in the web app. To update it from Android sources,
run `python tools/export_mobile_fishing_data.py` from this web repository while
it remains inside the Android project. Deployment needs only the generated
`aquawatch_app/static/aquawatch_app/fishing-data.json` and the web source files.

## Verify and deploy

1. Run `python aquawatch/manage.py collectstatic --noinput` before template tests;
   the project uses a manifest-backed static-file store.
2. Run `python aquawatch/manage.py test aquawatch_app --noinput`.
3. Run `node --test tests/fishing-features.test.mjs` (no npm packages required).
4. Run `python aquawatch/manage.py check` and
   `python aquawatch/manage.py makemigrations --check --dry-run`.

No new model migration is introduced. Existing migrations 0004 and 0005 are
still required for DeviceReading and the mobile API. Use the existing Render
deployment process; this workspace update does not publish the site or change
production records.
