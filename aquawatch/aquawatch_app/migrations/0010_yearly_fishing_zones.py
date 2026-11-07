from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('aquawatch_app','0009_fishingzone_exact_date_and_publication')]
    operations=[
        migrations.AddField(model_name='fishingzone',name='repeats_annually',field=models.BooleanField(
            default=True,
            help_text='Show this zone in the same month every year, starting with its exact date’s year. Turn off for a single-year zone.')),
    ]
