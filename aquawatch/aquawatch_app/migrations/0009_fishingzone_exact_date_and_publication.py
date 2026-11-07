from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('aquawatch_app', '0008_alert_device_alertdismissal')]

    operations = [
        migrations.RemoveIndex(model_name='fishingzone', name='zone_month_active'),
        migrations.RenameField(model_name='fishingzone', old_name='month', new_name='date'),
        migrations.AlterField(model_name='fishingzone', name='date', field=models.DateField(
            help_text='Exact date for this fishing zone, for example 2026-11-07.')),
        migrations.AlterModelOptions(name='fishingzone', options={'ordering': ['date', 'title', 'id']}),
        migrations.AddIndex(model_name='fishingzone', index=models.Index(fields=['date', 'active'], name='zone_date_active')),
        migrations.AddField(model_name='fishingzone', name='published_at', field=models.DateTimeField(
            null=True, blank=True, editable=False,
            help_text='Time this zone was first published. Older zones may have no recorded publication time.')),
    ]
