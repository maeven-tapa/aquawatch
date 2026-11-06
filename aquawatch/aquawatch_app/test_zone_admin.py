import json
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from .api import issue_token
from .models import FishingZone,Device
from .zone_geometry import validate_geometry

class ZoneAdministrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_superuser('zone-admin','admin@example.invalid','Zone-test-123!')
        cls.user=User.objects.create_user('zone-user','user@example.invalid','Zone-test-123!')
        cls.device=Device.objects.create(user=cls.user,name='User tracker',serial='ZONE-01')

    def auth(self,user):
        return {'HTTP_AUTHORIZATION':'Bearer '+issue_token(user)['token']}

    def payload(self,zone=None):
        zone=zone or FishingZone.objects.filter(month='2026-11-01').first()
        return {'title':'Edited fishing zone','month':'2026-11','center':{'lat':zone.latitude,'lng':zone.longitude},
                'boundary':zone.boundary,'version':zone.version,'active':True}

    def test_seed_has_all_monthly_counts_and_valid_water_shapes(self):
        for i,count in enumerate([14,11,18,13,20,16,12,17,15,16,10,13],1):
            zones=FishingZone.objects.filter(month=f'2026-{i:02d}-01')
            self.assertEqual(zones.count(),count)
            for zone in zones:
                self.assertAlmostEqual(validate_geometry(zone.boundary,zone.latitude,zone.longitude),zone.area_square_meters)

    def test_ordinary_user_reads_but_cannot_create_update_or_list_admin_records(self):
        headers=self.auth(self.user)
        self.assertEqual(self.client.get('/api/v1/fishing-zones/?month=2026-11',**headers).status_code,200)
        for path in ['/api/v1/fishing-zones/','/api/v1/fishing-zones/'+str(FishingZone.objects.first().pk)+'/']:
            self.assertEqual(self.client.post(path,json.dumps(self.payload()),content_type='application/json',**headers).status_code,403)
        for path in ['/api/v1/admin/users/','/api/v1/admin/devices/','/api/v1/admin/overview/']:
            self.assertEqual(self.client.get(path,**headers).status_code,403)

    def test_anonymous_reads_are_rejected(self):
        self.assertEqual(self.client.get('/api/v1/fishing-zones/?month=2026-11').status_code,401)

    def test_admin_edits_are_shared_on_web_mobile_and_django_admin(self):
        zone=FishingZone.objects.filter(month='2026-11-01').first()
        headers=self.auth(self.admin)
        response=self.client.post(f'/api/v1/fishing-zones/{zone.pk}/',json.dumps(self.payload(zone)),content_type='application/json',**headers)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['zone']['version'],2)
        other=self.client.get('/api/v1/fishing-zones/?month=2026-11',**self.auth(self.user)).json()
        self.assertIn('Edited fishing zone',[z['title'] for z in other['zones']])
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/map/?month=2026-11'),'Edited fishing zone')
        self.assertContains(self.client.get('/admin/aquawatch_app/fishingzone/',{'q':'Edited fishing zone'}),'Edited fishing zone')

    def test_stale_edits_do_not_overwrite_newer_shapes(self):
        zone=FishingZone.objects.first();body=self.payload(zone);headers=self.auth(self.admin)
        path=f'/api/v1/fishing-zones/{zone.pk}/'
        self.assertEqual(self.client.post(path,json.dumps(body),content_type='application/json',**headers).status_code,200)
        self.assertEqual(self.client.post(path,json.dumps(body),content_type='application/json',**headers).status_code,409)

    def test_land_and_crossing_shapes_rejected_by_both_model_and_api(self):
        body=self.payload();body['boundary'][0]={'lat':14.365,'lng':120.811}
        response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.status_code,400)
        with self.assertRaises(ValidationError):
            validate_geometry([{'lat':14.40,'lng':120.76},{'lat':14.42,'lng':120.78},
                               {'lat':14.42,'lng':120.76},{'lat':14.40,'lng':120.78}],14.41,120.77)

    def test_new_zone_area_and_publication_are_persisted(self):
        body=self.payload();body['month']='2027-01';body['active']=False
        response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.status_code,200,response.content)
        self.assertGreater(response.json()['zone']['area_square_meters'],100)
        self.assertEqual(self.client.get('/api/v1/fishing-zones/?month=2027-01',**self.auth(self.user)).json()['zones'],[])
        self.assertEqual(len(self.client.get('/api/v1/fishing-zones/?month=2027-01',**self.auth(self.admin)).json()['zones']),1)

    def test_web_admin_forms_require_csrf_and_staff_permissions(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post('/fishing-zones/',json.dumps(self.payload()),content_type='application/json').status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/fishing-zones/',json.dumps(self.payload()),content_type='application/json').status_code,403)
        self.assertEqual(self.client.get('/users/').status_code,403)

    def test_admin_sees_users_and_all_devices_without_exposing_passwords(self):
        headers=self.auth(self.admin)
        response=self.client.get('/api/v1/admin/users/',**headers)
        self.assertContains(response,'zone-user');self.assertNotContains(response,'password')
        response=self.client.get('/api/v1/admin/devices/',**headers)
        self.assertContains(response,'User tracker')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/devices/'),'User tracker')
        self.assertEqual(self.client.get(f'/devices/{self.device.pk}/').status_code,200)

    def test_administrator_flag_is_server_owned(self):
        self.assertFalse(issue_token(self.user)['snapshot']['user']['is_admin'])
        self.assertTrue(issue_token(self.admin)['snapshot']['user']['is_admin'])
        token=self.auth(self.admin)
        self.admin.is_staff=False;self.admin.is_superuser=False;self.admin.save()
        self.assertEqual(self.client.get('/api/v1/admin/users/',**token).status_code,403)
