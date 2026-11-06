import json
from datetime import date
from pathlib import Path
from django.db import migrations

def seed(apps,schema_editor):
    Zone=apps.get_model('aquawatch_app','FishingZone')
    rows=json.loads((Path(__file__).parent/'data/fishing-zones-2026.json').read_text(encoding='utf-8'))
    for row in rows:
        row['month']=date.fromisoformat(row['month'])
        Zone.objects.using(schema_editor.connection.alias).get_or_create(source_id=row.pop('source_id'),defaults=row)

class Migration(migrations.Migration):
    dependencies=[('aquawatch_app','0006_fishingzone')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
