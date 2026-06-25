from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Device, Report, UserProfile


class FeatureParityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='officer', password='safe-pass-123')
        UserProfile.objects.create(user=self.user)
        self.client.login(username='officer', password='safe-pass-123')

    def test_feature_pages_are_available(self):
        for name in ('dashboard', 'map', 'alerts', 'devices', 'reports', 'profile', 'settings'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_dashboard_uses_unified_live_conditions_panel(self):
        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Live conditions')
        self.assertContains(response, 'class="conditions-card full-width"')
        self.assertContains(response, 'class="condition-metric', count=6)
        self.assertNotContains(response, '<h2>Live weather</h2>')

    def test_incident_report_action_is_on_map_not_dashboard(self):
        dashboard_response = self.client.get(reverse('dashboard'))
        map_response = self.client.get(reverse('map'))

        self.assertNotContains(dashboard_response, 'Submit incident report')
        self.assertNotContains(dashboard_response, 'Officer profile')
        self.assertContains(map_response, 'Submit incident report')

    def test_incident_report_is_persisted(self):
        response = self.client.post(reverse('reports'), {
            'type': 'Distress signal', 'location': 'Manila Bay',
            'severity': 'High', 'description': 'Beacon observed offshore.',
        })
        self.assertRedirects(response, reverse('reports'))
        self.assertTrue(Report.objects.filter(user=self.user, type='Distress signal').exists())

    def test_device_details_are_scoped_to_owner(self):
        device = Device.objects.create(user=self.user, name='Tracker 1', serial='AW-1')
        self.assertEqual(self.client.get(reverse('device_detail', args=[device.id])).status_code, 200)

    def test_device_registration_saves_and_shows_modules(self):
        response = self.client.post(reverse('add_device'), {
            'name': 'Sensor Card 1',
            'device_type': 'Water level monitoring card',
            'water_level': 'on',
            'gyro': 'on',
            'gsm': 'on',
            'gps': 'on',
            'serial': 'AW-CARD-1',
            'status': 'Active',
        })

        self.assertRedirects(response, reverse('devices'))
        device = Device.objects.get(user=self.user, serial='AW-CARD-1')
        self.assertEqual(device.capability_labels, ['Water Level', 'Gyro', 'GSM', 'GPS'])

        devices_response = self.client.get(reverse('devices'))
        self.assertContains(devices_response, 'Water Level')
        self.assertContains(devices_response, 'Gyro')
        self.assertContains(devices_response, 'GSM')
        self.assertContains(devices_response, 'GPS')

    def test_settings_are_persisted(self):
        response = self.client.post(reverse('settings'), {
            'notifications_enabled': 'on', 'share_location': 'on',
            'alert_sound': 'Silent', 'language': 'Filipino',
        })
        self.assertRedirects(response, reverse('settings'))
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.language, 'Filipino')
        self.assertFalse(profile.dark_mode)
