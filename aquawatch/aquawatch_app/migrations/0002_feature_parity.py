from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('aquawatch_app', '0001_initial')]

    operations = [
        migrations.AddField(model_name='userprofile', name='notifications_enabled', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='userprofile', name='share_location', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='userprofile', name='alert_sound', field=models.CharField(default='Standard Marine Tone', max_length=64)),
        migrations.AddField(model_name='userprofile', name='profile_image', field=models.FileField(blank=True, upload_to='profiles/')),
        migrations.AddField(model_name='device', name='device_type', field=models.CharField(default='GPS tracker', max_length=128)),
        migrations.AddField(model_name='device', name='imei', field=models.CharField(blank=True, max_length=128)),
        migrations.AddField(model_name='device', name='driver', field=models.CharField(blank=True, max_length=128)),
        migrations.AddField(model_name='device', name='photo', field=models.FileField(blank=True, upload_to='devices/')),
    ]
