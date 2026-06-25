from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('aquawatch_app', '0002_feature_parity')]

    operations = [
        migrations.AddField(model_name='device', name='water_level', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='device', name='gyro', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='device', name='gsm', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='device', name='gps', field=models.BooleanField(default=True)),
    ]
