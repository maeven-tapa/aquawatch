import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .accounts import EMAIL_ALREADY_REGISTERED
from .forms import AccountForm, COAST_GUARD_RANKS
from .models import MonitoringArea, UserProfile


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
)
class SharedAccountTests(TestCase):
    password = 'Sailing!Future2026'

    def web_data(self, email='new@example.com', username='new-officer'):
        return {'username': username, 'email': email, 'password1': self.password,
                'password2': self.password, 'role': COAST_GUARD_RANKS[0][0],
                'accepted_terms': True, 'first_name': 'Maeve', 'last_name': 'Tapa',
                'station': 'Manila', 'phone': '09123456789'}

    def api_post(self, name, data):
        return Client().post(reverse(name), json.dumps(data), content_type='application/json')

    def test_web_signup_creates_shared_account_and_mobile_can_login(self):
        response = self.client.post(reverse('register'), self.web_data(' NEW@Example.com '))
        self.assertRedirects(response, reverse('location'))
        user = User.objects.get(username='new-officer')
        self.assertEqual(user.email, 'new@example.com')
        self.assertEqual(user.first_name, 'Maeve')
        self.assertEqual(UserProfile.objects.get(user=user).station, 'Manila')
        self.assertTrue(MonitoringArea.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        response = self.api_post('api_login', {'email': 'NEW@example.com', 'password': self.password})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['snapshot']['user']['id'], user.pk)

    def test_web_signup_requires_email(self):
        response = self.client.post(reverse('register'), self.web_data(''))
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertFalse(User.objects.exists())

    def test_web_account_blocks_second_web_or_mobile_registration(self):
        self.client.post(reverse('register'), self.web_data())
        self.client.logout()
        response = self.client.post(reverse('register'), self.web_data(' NEW@EXAMPLE.COM ', 'different-officer'))
        self.assertContains(response, EMAIL_ALREADY_REGISTERED)
        for name in ('api_request_code', 'api_register'):
            response = self.api_post(name, {'email': ' NEW@EXAMPLE.COM ', 'accepted_terms': True})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['error'], EMAIL_ALREADY_REGISTERED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_mobile_account_blocks_second_web_registration(self):
        self.assertEqual(self.api_post('api_request_code', {'email': 'mobile@example.com'}).status_code, 200)
        code = mail.outbox[-1].body.split(' is ')[1][:6]
        response = self.api_post('api_register', {'email': 'MOBILE@example.com', 'password': self.password,
                                                'accepted_terms': True, 'code': code})
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('register'), self.web_data(' MOBILE@EXAMPLE.COM '))
        self.assertContains(response, EMAIL_ALREADY_REGISTERED)
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(self.client.login(username='mobile@example.com', password=self.password))

    def test_web_signup_after_code_issue_blocks_later_mobile_signup(self):
        self.api_post('api_request_code', {'email': 'new@example.com'})
        code = mail.outbox[-1].body.split(' is ')[1][:6]
        self.client.post(reverse('register'), self.web_data())
        response = self.api_post('api_register', {'email': 'new@example.com', 'password': self.password,
                                                'accepted_terms': True, 'code': code})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(User.objects.count(), 1)

    def test_database_rejects_duplicate_insert_after_both_clients_precheck(self):
        User.objects.create_user(username='first', email='shared@example.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='second', email=' SHARED@EXAMPLE.COM ')
        self.assertEqual(User.objects.count(), 1)

    def test_web_duplicate_race_returns_email_error(self):
        with patch('aquawatch_app.views.UserRegistrationForm.save', side_effect=IntegrityError), \
                patch('aquawatch_app.views.email_is_registered', return_value=True):
            response = self.client.post(reverse('register'), self.web_data())
        self.assertContains(response, EMAIL_ALREADY_REGISTERED)
        self.assertIn('email', response.context['form'].errors)
        self.assertFalse(User.objects.exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_profile_cannot_take_another_accounts_email(self):
        first = User.objects.create_user(username='first', email='first@example.com')
        other = User.objects.create_user(username='other', email='other@example.com')
        self.client.force_login(first)
        response = self.client.post(reverse('profile'), {'action': 'profile', 'email': ' OTHER@EXAMPLE.COM ',
                                                       'role': COAST_GUARD_RANKS[0][0]})
        self.assertContains(response, EMAIL_ALREADY_REGISTERED)
        first.refresh_from_db()
        self.assertEqual(first.email, 'first@example.com')
        form = AccountForm({'email': ' FIRST@EXAMPLE.COM '}, instance=first)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().email, 'first@example.com')
        other.refresh_from_db()
        self.assertEqual(other.email, 'other@example.com')

    def test_profile_duplicate_race_returns_email_error(self):
        user = User.objects.create_user(username='officer', email='officer@example.com')
        UserProfile.objects.create(user=user)
        self.client.force_login(user)
        with patch('aquawatch_app.views.AccountForm.save', side_effect=IntegrityError), \
                patch('aquawatch_app.views.email_is_registered', return_value=True):
            response = self.client.post(reverse('profile'), {'action': 'profile', 'email': 'new@example.com',
                                                           'role': COAST_GUARD_RANKS[0][0]})
        self.assertContains(response, EMAIL_ALREADY_REGISTERED)
        user.refresh_from_db()
        self.assertEqual(user.email, 'officer@example.com')


class EmailUniquenessMigrationTests(TransactionTestCase):
    previous = [('aquawatch_app', '0004_devicereading_mobileauthwindow_mobiletoken_and_more')]
    current = [('aquawatch_app', '0005_unique_account_email')]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        self.User = executor.loader.project_state(self.previous).apps.get_model('auth', 'User')

    def tearDown(self):
        # Restore the latest schema before Django flushes this disposable database.
        self.User.objects.all().delete()
        MigrationExecutor(connection).migrate(self.current)
        super().tearDown()

    def test_existing_duplicates_stop_migration_without_changing_accounts(self):
        first = self.User.objects.create(username='first', email=' Shared@Example.com ')
        second = self.User.objects.create(username='second', email='shared@example.com')
        with self.assertRaisesMessage(RuntimeError, 'existing accounts share an email'):
            MigrationExecutor(connection).migrate(self.current)
        self.assertEqual(self.User.objects.count(), 2)
        self.assertEqual(self.User.objects.get(pk=first.pk).email, ' Shared@Example.com ')
        self.assertEqual(self.User.objects.get(pk=second.pk).email, 'shared@example.com')

    def test_upgrade_preserves_accounts_and_normalizes_email(self):
        user = self.User.objects.create(username='existing', email=' Officer@Example.com ')
        self.User.objects.create(username='legacy-one', email='')
        self.User.objects.create(username='legacy-two', email='')
        MigrationExecutor(connection).migrate(self.current)
        self.assertEqual(self.User.objects.get(pk=user.pk).email, 'officer@example.com')
        self.assertEqual(self.User.objects.count(), 3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.User.objects.create(username='duplicate', email='OFFICER@EXAMPLE.COM')
