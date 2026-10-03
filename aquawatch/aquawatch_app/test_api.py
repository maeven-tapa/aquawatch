import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Alert, Device, DeviceReading, MobileToken, MonitoringArea, Report, SignupChallenge, SyncReceipt, UserProfile


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class MobileApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='officer', email='officer@example.com', password='Harbor!Storm2026')
        self.other = User.objects.create_user(username='other', email='other@example.com', password='Harbor!Storm2026')
        self.client = Client(enforce_csrf_checks=True)
        response = self.post('api_login', {'email': self.user.email, 'password': 'Harbor!Storm2026'})
        self.token = response.json()['token']
        self.auth = {'HTTP_AUTHORIZATION': 'Bearer ' + self.token}

    def post(self, name, data, auth=None):
        return self.client.post(reverse(name), json.dumps(data), content_type='application/json', **(auth or {}))

    def event(self, event_id, kind, data):
        return {'id': event_id, 'kind': kind, 'data': data}

    def sync(self, events):
        return self.post('api_sync', {'events': events}, self.auth)

    def device(self):
        return self.event('device-event', 'device.upsert', {'id': 'phone-1', 'name': 'Boat 1', 'serial': 'AW-001', 'type': 'GPS tracker'})

    def reading(self, event_id='reading-event', **updates):
        data = {'device_id': 'phone-1', 'received_at': int(timezone.now().timestamp() * 1000),
                'latitude': 14.5, 'longitude': 120.9, 'gyro_x': '2.4', 'gyro_y': '-1.8',
                'gsm_signal': '-80 dBm', 'acceleration': '0.5 m/s2', 'alert_type': 'SOS', 'is_distress': False}
        data.update(updates)
        return self.event(event_id, 'reading.create', data)

    def report(self):
        return self.event('report-event', 'report.create', {'id': 'report-1', 'type': 'Incident', 'location': 'Manila Bay',
            'severity': 'High', 'description': 'Vessel needs assistance.', 'created_at': int(timezone.now().timestamp() * 1000)})

    def test_health_and_json_method_validation(self):
        self.assertEqual(self.client.get(reverse('api_health')).json()['api_version'], 1)
        self.assertEqual(self.client.get(reverse('api_login')).status_code, 405)
        self.assertEqual(self.client.post(reverse('api_login'), {}).status_code, 415)
        self.assertEqual(self.client.post(reverse('api_login'), '{bad', content_type='application/json').status_code, 400)
        self.assertEqual(self.post('api_login', []).status_code, 400)

    def test_mobile_login_shares_web_account_without_csrf_cookie(self):
        self.assertEqual(self.post('api_login', {'email': 'OFFICER@example.com', 'password': 'Harbor!Storm2026'}).status_code, 200)
        self.assertEqual(self.post('api_login', {'email': 'officer', 'password': 'Harbor!Storm2026'}).status_code, 200)
        self.assertEqual(self.post('api_login', {'email': self.user.email, 'password': 'wrong'}).status_code, 401)
        self.assertEqual(MobileToken.objects.get(digest=hashlib.sha256(self.token.encode()).hexdigest()).user, self.user)
        self.assertFalse(MobileToken.objects.filter(digest=self.token).exists())

    def test_duplicate_email_cannot_be_assigned_to_another_account(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.other.pk).update(email=' OFFICER@EXAMPLE.COM ')
        self.other.refresh_from_db()
        self.assertEqual(self.other.email, 'other@example.com')
        self.assertEqual(self.post('api_login', {'email': self.user.email, 'password': 'Harbor!Storm2026'}).status_code, 200)

    def test_inactive_user_cannot_login_or_use_token(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.post('api_login', {'email': self.user.email, 'password': 'Harbor!Storm2026'}).status_code, 401)
        self.assertEqual(self.client.get(reverse('api_sync'), **self.auth).status_code, 401)

    def test_sync_requires_token_even_for_logged_in_browser(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('api_sync')).status_code, 401)

    def test_expiry_password_change_and_logout_revoke_tokens(self):
        self.user.set_password('Different!Harbor2026')
        self.user.save()
        self.assertEqual(self.client.get(reverse('api_sync'), **self.auth).status_code, 401)
        self.user.set_password('Harbor!Storm2026')
        self.user.save()
        response = self.post('api_login', {'email': 'officer', 'password': 'Harbor!Storm2026'})
        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + response.json()['token']}
        self.assertEqual(self.post('api_logout', {}, auth).status_code, 200)
        self.assertEqual(self.client.get(reverse('api_sync'), **auth).status_code, 401)
        MobileToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(reverse('api_sync'), **self.auth).status_code, 401)

    def test_reports_and_devices_appear_in_existing_web_pages(self):
        self.assertEqual(self.sync([self.device(), self.report()]).status_code, 200)
        browser = Client()
        browser.force_login(self.user)
        self.assertContains(browser.get(reverse('devices')), 'Boat 1')
        self.assertContains(browser.get(reverse('reports')), 'Vessel needs assistance.')

    def test_retry_does_not_duplicate_reports_readings_or_alerts(self):
        events = [self.device(), self.report(), self.reading()]
        for _ in range(2):
            self.assertEqual(self.sync(events).status_code, 200)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(DeviceReading.objects.count(), 1)
        self.assertEqual(Alert.objects.count(), 1)
        self.assertEqual(SyncReceipt.objects.count(), 3)

    def test_event_id_cannot_be_reused_with_new_data(self):
        self.assertEqual(self.sync([self.device()]).status_code, 200)
        modified = self.device()
        modified['data']['name'] = 'Changed'
        self.assertEqual(self.sync([modified]).status_code, 409)
        self.assertEqual(Device.objects.get().name, 'Boat 1')

    def test_invalid_batch_rolls_back_receipts_and_writes(self):
        response = self.sync([self.device(), self.reading(latitude=100)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['failed_event_id'], 'reading-event')
        self.assertFalse(Device.objects.exists())
        self.assertFalse(SyncReceipt.objects.exists())

    def test_one_user_cannot_read_or_modify_another_users_device(self):
        foreign = Device.objects.create(user=self.other, name='Private', serial='PRIVATE', mobile_id='other-phone')
        response = self.client.get(reverse('api_sync'), **self.auth)
        self.assertEqual(response.json()['snapshot']['devices'], [])
        self.assertEqual(self.sync([self.reading(device_id='other-phone')]).status_code, 400)
        self.assertEqual(self.sync([self.event('foreign', 'device.upsert', {'id': f'web-{foreign.pk}', 'serial': 'PRIVATE'})]).status_code, 400)
        self.assertEqual(DeviceReading.objects.count(), 0)

    def test_existing_web_device_links_by_serial(self):
        original = Device.objects.create(user=self.user, name='Web boat', serial='AW-001', gyro=False)
        self.assertEqual(self.sync([self.device(), self.reading()]).status_code, 200)
        original.refresh_from_db()
        self.assertEqual(original.mobile_id, 'phone-1')
        self.assertFalse(original.gyro)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(original.status, 'Active')
        self.assertEqual(original.last_location, '14.5, 120.9')

    def test_old_reading_does_not_replace_latest_position(self):
        now = int(timezone.now().timestamp() * 1000)
        self.assertEqual(self.sync([self.device(), self.reading(received_at=now)]).status_code, 200)
        self.assertEqual(self.sync([self.reading('older', received_at=now-60_000, latitude=13.0)]).status_code, 200)
        self.assertEqual(Device.objects.get().last_location, '14.5, 120.9')
        self.assertEqual(DeviceReading.objects.count(), 2)

    def test_invalid_coordinates_timestamps_and_boolean_are_rejected(self):
        self.assertEqual(self.sync([self.device()]).status_code, 200)
        for invalid in ({'latitude': float('nan')}, {'longitude': 181}, {'received_at': 'now'}, {'is_distress': 'false'}):
            self.assertEqual(self.sync([self.reading(**invalid)]).status_code, 400)

    def test_profile_and_area_sync(self):
        response = self.sync([self.event('profile', 'profile.update', {'first_name': 'Maeve', 'phone': '09123456789'}),
                              self.event('area', 'area.update', {'latitude': 14.5, 'longitude': 120.9, 'label': 'Watch zone'})])
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Maeve')
        self.assertEqual(MonitoringArea.objects.get(user=self.user).label, 'Watch zone')

    def test_signup_requires_server_issued_code_and_creates_web_account(self):
        self.assertEqual(self.post('api_request_code', {'email': 'new@example.com'}).status_code, 200)
        from django.core import mail
        code = mail.outbox[-1].body.split(' is ')[1][:6]
        data = {'email': 'new@example.com', 'password': 'Sailing!Future2026', 'accepted_terms': True, 'code': '000000'}
        self.assertEqual(self.post('api_register', data).status_code, 400)
        self.assertEqual(SignupChallenge.objects.get(email=data['email']).attempts, 1)
        data['code'] = code
        response = self.post('api_register', data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.get(email=data['email']).check_password(data['password']))
        self.assertFalse(SignupChallenge.objects.filter(email=data['email']).exists())
        browser = Client()
        self.assertTrue(browser.login(username=data['email'], password=data['password']))

    def test_signup_stops_after_five_wrong_codes(self):
        self.post('api_request_code', {'email': 'new@example.com'})
        data = {'email': 'new@example.com', 'password': 'Sailing!Future2026', 'accepted_terms': True, 'code': '000000'}
        for _ in range(6):
            self.assertEqual(self.post('api_register', data).status_code, 400)
        self.assertEqual(SignupChallenge.objects.get(email=data['email']).attempts, 5)

    def test_password_change_is_shared_and_revokes_previous_session(self):
        response = self.post('api_password', {'current_password': 'Harbor!Storm2026', 'new_password': 'Sailing!Future2026'}, self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse('api_sync'), **self.auth).status_code, 401)
        fresh = {'HTTP_AUTHORIZATION': 'Bearer ' + response.json()['token']}
        self.assertEqual(self.client.get(reverse('api_sync'), **fresh).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Sailing!Future2026'))

    def test_auth_throttle_persists_in_database(self):
        statuses = [self.post('api_login', {'email': 'nonexistent', 'password': 'wrong'}).status_code for _ in range(16)]
        self.assertEqual(statuses[-1], 429)

    def test_batch_limit_and_unknown_event(self):
        self.assertEqual(self.sync([self.device()] * 101).status_code, 400)
        self.assertEqual(self.sync([self.event('bad', 'unknown', {})]).status_code, 400)

    def test_password_whitespace_is_preserved(self):
        self.user.set_password(' Harbor!Storm2026 ')
        self.user.save()
        self.assertEqual(self.post('api_login', {'email': 'officer', 'password': ' Harbor!Storm2026 '}).status_code, 200)
        self.assertEqual(self.post('api_login', {'email': 'officer', 'password': 'Harbor!Storm2026'}).status_code, 401)

    def test_failed_event_can_be_isolated_without_blocking_other_uploads(self):
        bad = self.reading(latitude=100)
        response = self.sync([self.device(), bad, self.report()])
        self.assertEqual(response.json()['failed_event_id'], bad['id'])
        self.assertEqual(self.sync([self.device(), self.report()]).status_code, 200)
        self.assertEqual(Report.objects.count(), 1)
        self.assertFalse(DeviceReading.objects.exists())

    def test_web_edits_and_alerts_are_available_to_android(self):
        device = Device.objects.create(user=self.user, name='Web boat', serial='WEB-1')
        Alert.objects.create(user=self.user, type='Storm', location='Manila Bay', time='Now', severity='High')
        response = self.client.get(reverse('api_sync'), **self.auth).json()['snapshot']
        self.assertEqual(response['devices'][0]['id'], f'web-{device.pk}')
        self.assertEqual(response['devices'][0]['server_id'], device.pk)
        self.assertEqual(response['alerts'][0]['type'], 'Storm')

    def test_stale_status_becomes_offline_and_source_alert_id_is_stable(self):
        now = int(timezone.now().timestamp() * 1000)
        event = self.reading(received_at=now - 15 * 60_000)
        response = self.sync([self.device(), event]).json()['snapshot']
        self.assertEqual(Device.objects.get().status, 'Offline')
        self.assertEqual(response['alerts'][0]['id'], f'phone-1-{event["data"]["received_at"]}')
