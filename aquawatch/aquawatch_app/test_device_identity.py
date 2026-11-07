from django.contrib.auth.models import User
from django.test import TestCase
from .models import Device,DeviceReading
from .api import issue_token
from django.utils import timezone

class DeviceIdentityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner=User.objects.create_user('maria','maria@example.invalid','Device-test-123!',first_name='Maria',last_name='Santos')
        cls.admin=User.objects.create_superuser('device-admin','device-admin@example.invalid','Device-test-123!')
        cls.device=Device.objects.create(user=cls.owner,name='Amaya Tracker 07',serial='AW-007',
            owner='Juan Dela Cruz',driver='Pedro',vessel='Bangka Uno',registration='CV-007',
            imei='123456789012345',sim='+639171234567',contact='+639181234567',last_updated='SOS received 10:30 AM')
        DeviceReading.objects.create(device=cls.device,received_at=timezone.now(),latitude=14.41,longitude=120.78,alert_type='SOS')

    def test_admin_device_response_separates_account_and_device_owner(self):
        token=issue_token(self.admin)['token']
        response=self.client.get('/api/v1/admin/devices/',HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(response.status_code,200)
        row=response.json()['devices'][0]
        self.assertEqual(row['name'],'Amaya Tracker 07')
        self.assertEqual(row['account']['name'],'Maria Santos')
        self.assertEqual(row['account']['username'],'maria')
        self.assertEqual(row['owner_name'],'Juan Dela Cruz')
        self.assertEqual(row['vessel'],'Bangka Uno')
        self.assertEqual(row['registration'],'CV-007')
        self.assertNotIn('password',row['account'])

    def test_web_list_and_details_show_registration_identity_even_with_an_sos(self):
        for user in (self.owner,self.admin):
            self.client.force_login(user)
            response=self.client.get('/devices/')
            self.assertContains(response,'Amaya Tracker 07')
            self.assertContains(response,'Maria Santos')
            self.assertContains(response,'Juan Dela Cruz')
            response=self.client.get(f'/devices/{self.device.pk}/')
            self.assertContains(response,'<h1>Amaya Tracker 07</h1>',html=True)
            for text in ('Owning account','Maria Santos','maria@example.invalid','Device information','Serial number','AW-007','Juan Dela Cruz','Bangka Uno','CV-007'):
                self.assertContains(response,text)

    def test_other_accounts_cannot_read_private_device_details(self):
        other=User.objects.create_user('other-device-user',password='Device-test-123!')
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/devices/{self.device.pk}/').status_code,404)
