# Fishing features shared with Android

The map preserves the original 175 illustrative Amaya-area polygons across the
12 monthly catalogs, with fish markers, six habitat profiles, and source links.
Select a marker, polygon, or area
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

Apply migration 0009 for exact fishing-zone dates and publication timestamps,
then 0010 for yearly repetition. These migrations preserve the original zone data.
Existing migrations are still required for DeviceReading and the mobile API. Use the existing Render
deployment process; this workspace update does not publish the site or change
production records.

## Exact zone dates and publication

Both the Django admin and map editor accept an exact `YYYY-MM-DD` zone date.
Monthly map browsing includes every zone dated within the selected month. Each
zone's details show its selected date and first-publication time in Asia/Manila.
The publication timestamp is set by the server when a new zone is published or a
draft is first activated, and stays unchanged through edits and republication.
Existing records retain their original dates; their historical publication time
is shown as unavailable because it was not previously recorded.

The Django admin now includes a map with the configured fishing-area outline,
draggable boundary vertices and center pin, a valid starter boundary, and a
center-pin repair button. Both editors show the allowed area as a dashed outline.
Out-of-area coordinates identify the offending boundary point. The configured
area remains an application constraint, rather than a surveyed coastline.

The zone API accepts `date` on writes and returns `date` and `published_at`.
`published_at` is read-only. The `month` request/response value remains supported
for older mobile clients and monthly filtering. A month-only edit within the
same month preserves an existing exact day; moving to another month via that
legacy input uses its first day. Updated clients should send `date`.

## Yearly fishing zones

Zones default to **Repeat every year** in both admin editors. A zone dated
November 17, 2026 appears in November 2026, November 2027 and later Novembers.
Turn off repetition for a single-year entry. Zones never appear before their
original year, and unpublished zones remain visible only to administrators.
Use **Choose month and year** on the map to jump directly to next November.

Web and API reads share the same monthly selection. The API returns
`repeats_annually` and `occurrence_date` for the selected year, while `date` and
`published_at` retain their original values. A leap-day zone uses February 28
in non-leap years. Reads do not create duplicate database records. Editing or
unpublishing a recurring zone affects all its yearly appearances.

Migration 0010 adds yearly repetition without inserting any zones. The original
2026 seed and catalog remain intact, including their monthly counts and shapes.


## OpenStreetMap tile identification

The web application explicitly uses `strict-origin-when-cross-origin` as its
Django Referrer-Policy and on Leaflet tile images. Django's default `same-origin`
header had suppressed Referer on requests to tile.openstreetmap.org, which can
trigger OSM's blocked-tile response. Cross-origin requests now send the website
origin, without device-detail paths or query parameters. Keep that header intact
at the hosting proxy/CDN and retain the visible OpenStreetMap attribution.

The shared basemap helper covers fishing maps, the shape editor and device
history. Tile failures show a readable message and transparent failed tiles,
while zone outlines and GPS overlays remain usable. There are no proxy workarounds,
cache-busting URLs, alternate volunteer tile host rotations, prefetches or bulk
downloads. The helper uses normal browser caching and updates on idle while
panning. Apply changes with the usual deployment plus collectstatic, then reload
the page. A provider-side IP block may still require contacting the provider.

`tools/verify_map_tiles_preview.mjs` checks the actual browser-generated Referer,
per-image policy, 403 handling and working overlays with intercepted tile
requests. It deliberately does not download public tiles during automated tests.
Reference: https://operations.osmfoundation.org/policies/tiles/
