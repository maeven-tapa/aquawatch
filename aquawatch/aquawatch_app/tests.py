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

    def test_settings_are_persisted(self):
        response = self.client.post(reverse('settings'), {
            'notifications_enabled': 'on', 'share_location': 'on',
            'alert_sound': 'Silent', 'language': 'Filipino',
        })
        self.assertRedirects(response, reverse('settings'))
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.language, 'Filipino')
        self.assertFalse(profile.dark_mode)
