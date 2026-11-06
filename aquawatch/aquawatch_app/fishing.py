"""Bundled regional information and explicitly synthetic history for display.

Sample rows never enter DeviceReading, alerts, live positions, or sync receipts.
"""
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import Device


@lru_cache(maxsize=1)
def fishing_catalog():
    path = Path(__file__).parent / 'static/aquawatch_app/fishing-data.json'
    return json.loads(path.read_text(encoding='utf-8'))


def device_status_history(device):
    rows = []
    first_id = Device.objects.filter(user_id=device.user_id).order_by('pk').values_list('pk', flat=True).first()
    if first_id == device.pk:
        rows.extend(dict(row, id=f'sample-{row["receivedAt"]}') for row in fishing_catalog()['sampleHistory'])
    for reading in device.readings.order_by('-received_at', '-pk')[:500]:
        rows.append({
            'id': f'reading-{reading.pk}', 'receivedAt': int(reading.received_at.timestamp() * 1000),
            'latitude': reading.latitude, 'longitude': reading.longitude,
            'gyroX': reading.gyro_x, 'gyroY': reading.gyro_y, 'isSample': False,
            'isDistress': reading.is_distress, 'alertType': reading.alert_type,
        })
    for row in rows:
        local = datetime.fromtimestamp(row['receivedAt'] / 1000, ZoneInfo('Asia/Manila'))
        row['dateKey'] = local.date().isoformat()
        row['receivedLabel'] = f'{local:%b} {local.day}, {local.year} · {local:%I:%M %p}'
    return sorted(rows, key=lambda row: row['receivedAt'], reverse=True)
