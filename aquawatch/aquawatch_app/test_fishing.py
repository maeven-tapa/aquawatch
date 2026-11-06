from datetime import datetime, timezone

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .fishing import device_status_history, fishing_catalog
from .models import Alert, Device, DeviceReading


class FishingFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fish-test', password='fixture-pass-123')
        self.device = Device.objects.create(user=self.user, name='Existing tracker', serial='EXISTING')
        self.client.force_login(self.user)

    def test_existing_first_device_gets_175_display_samples_without_sensor_or_alert_writes(self):
        for _ in range(2):
            response = self.client.get(reverse('device_detail', args=[self.device.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['sample_count'], 175)
            self.assertEqual(len(response.context['history']), 175)
            self.assertContains(response, '175 labeled sample logs')
            self.assertContains(response, 'October 1–28, 2026')
        self.assertEqual(DeviceReading.objects.count(), 0)
        self.assertEqual(Alert.objects.count(), 0)
        self.device.refresh_from_db()
        self.assertIsNone(self.device.last_status_at)
        self.assertEqual(self.device.last_location, '')

    def test_real_readings_are_preserved_and_samples_are_only_on_the_first_owned_device(self):
        DeviceReading.objects.create(device=self.device, received_at=datetime(2026, 11, 6, 5, tzinfo=timezone.utc),
                                     latitude=14.4, longitude=120.82, gyro_x='2.4', gyro_y='-1.8')
        second = Device.objects.create(user=self.user, name='Second', serial='SECOND')
        rows = device_status_history(self.device)
        self.assertEqual(len(rows), 176)
        self.assertFalse(rows[0]['isSample'])
        self.assertEqual(rows[0]['dateKey'], '2026-11-06')
        self.assertEqual(device_status_history(second), [])
        self.assertEqual(DeviceReading.objects.count(), 1)

    def test_history_is_owner_scoped(self):
        other = User.objects.create_user(username='other-fish-test', password='fixture-pass-123')
        device = Device.objects.create(user=other, name='Private tracker', serial='PRIVATE')
        self.assertEqual(self.client.get(reverse('device_detail', args=[device.pk])).status_code, 404)

    def test_map_has_all_polygons_profiles_sources_and_trip_controls(self):
        response = self.client.get(reverse('map'), {'month':'2026-11'})
        self.assertEqual(len(response.context['fishing_data']['zones']), 10)
        self.assertEqual(len(response.context['fishing_data']['fish']), 6)
        self.assertContains(response, 'Fishing efficiency & tides')
        self.assertContains(response, 'municipal limits and fish presence are unverified')
        self.assertNotContains(response, '500 m radius')
        self.assertContains(response, 'fishing-map.')
        self.assertEqual(len(fishing_catalog()['sampleHistory']), 175)
