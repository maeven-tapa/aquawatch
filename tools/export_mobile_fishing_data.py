"""Refresh the web's bundled catalog from the Android feature sources.

Run from anywhere with the mobile and web folders in their current layout.
The deployed web app consumes only the resulting JSON, not the Android files.
"""
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1]
MOBILE = WEB_ROOT.parent / 'app/src/main/java/com/example/aquawatch/ui/screens'
OUTPUT = WEB_ROOT / 'aquawatch/aquawatch_app/static/aquawatch_app/fishing-data.json'
STRING = r'"(?:[^"\\]|\\.)*"'


def source_pairs(body):
    return [{'title': json.loads(title), 'url': json.loads(url)} for title, url in
            re.findall(rf'FishHabitatSource\(\s*({STRING}),\s*({STRING})\s*\)', body)]


def export():
    zones_source = (MOBILE / 'AmayaFishingZones.kt').read_text(encoding='utf-8')
    zones = []
    pattern = rf'habitatArea\(({STRING}),\s*({STRING}),\s*([\d.]+),\s*([\d.]+),\s*(.*?)\)'
    for identifier, title, latitude, longitude, body in re.findall(pattern, zones_source, re.S):
        lat, lng = float(latitude), float(longitude)
        offsets = [(int(e), int(n)) for e, n in re.findall(r'(-?\d+) to (-?\d+)', body)]
        zones.append({
            'id': json.loads(identifier), 'title': json.loads(title), 'center': {'lat': lat, 'lng': lng},
            'boundary': [{'lat': lat + n / 111320, 'lng': lng + e / (111320 * math.cos(math.radians(lat)))}
                         for e, n in offsets], 'proposed': True,
        })
    fish_source = (MOBILE / 'AmayaFishHabitats.kt').read_text(encoding='utf-8')
    fish = []
    for block in fish_source.split('FishHabitatProfile(')[2:]:
        fields = {key: json.loads(value) for key, value in
                  re.findall(rf'\b(id|localName|identification|habitat|note)\s*=\s*({STRING})', block)}
        if fields.get('id'):
            fields['source'] = source_pairs(block)[0]
            fish.append(fields)
    sources = {}
    for name, output_name in [('TanzaWaterSources', 'waters'), ('CaviteFishCatchSources', 'catches')]:
        block = re.search(rf'internal val {name} = listOf\((.*?)\n\)', fish_source, re.S).group(1)
        sources[output_name] = source_pairs(block)
    naming = re.search(r'internal val SalinasNamingSource = (FishHabitatSource\(.*?\n\))', fish_source, re.S).group(1)
    sources['salinas'] = source_pairs(naming)[0]
    samples = []
    for day in range(16, 30):
        index = day - 16
        times = [13 * 60 + index * 9 % 50]
        if day in {16, 18, 21, 25, 29}:
            times.append(16 * 60 + index * 11 % 55)
        times.append(20 * 60 if day == 29 else 18 * 60 + 30 + index * 17 % 90)
        for reading, minute in enumerate(times):
            sequence = len(samples)
            samples.append({
                'receivedAt': int(datetime(2026, 10, day, minute // 60, minute % 60,
                                           tzinfo=timezone(timedelta(hours=8))).timestamp() * 1000),
                'latitude': 14.394530 + index % 4 * .0012 + reading * .0006,
                'longitude': 120.825889 - .002 - index * .0007 - reading * .002,
                'gyroX': f'{((sequence * 17) % 89 - 44) / 10:.1f}',
                'gyroY': f'{((sequence * 13) % 71 - 35) / 10:.1f}',
                'isSample': True, 'isDistress': False, 'alertType': '',
            })
    assert len(zones) == 11 and len(fish) == 6 and len(samples) == 33
    OUTPUT.write_text(json.dumps({'version': 1, 'timeZone': 'Asia/Manila', 'zones': zones, 'fish': fish,
                                  'sources': sources, 'sampleHistory': samples}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Exported {len(zones)} polygons, {len(fish)} fish profiles and {len(samples)} sample logs.')


if __name__ == '__main__':
    export()
