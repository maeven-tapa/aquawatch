import json
from datetime import date
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
        zone=zone or FishingZone.objects.filter(date='2026-11-01').first()
        return {'title':'Edited fishing zone','month':'2026-11','center':{'lat':zone.latitude,'lng':zone.longitude},
                'boundary':zone.boundary,'version':zone.version,'active':True}

    def test_seed_has_all_monthly_counts_and_valid_water_shapes(self):
        for i,count in enumerate([14,11,18,13,20,16,12,17,15,16,10,13],1):
            zones=FishingZone.objects.filter(date=f'2026-{i:02d}-01')
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
        zone=FishingZone.objects.filter(date='2026-11-01').first()
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
        ordinary=self.client.get('/api/v1/fishing-zones/?month=2027-01',**self.auth(self.user)).json()['zones']
        self.assertNotIn(response.json()['zone']['id'],[z['id'] for z in ordinary])
        self.assertEqual(len(ordinary),14)
        self.assertEqual(len(self.client.get('/api/v1/fishing-zones/?month=2027-01',**self.auth(self.admin)).json()['zones']),15)

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

    def test_exact_dates_are_saved_and_included_in_monthly_web_and_api_results(self):
        body=self.payload();body['date']='2027-01-17'
        response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.status_code,200,response.content)
        created=response.json()['zone']
        self.assertEqual(created['date'],'2027-01-17')
        self.assertEqual(created['month'],'2027-01')
        self.assertIsNotNone(created['published_at'])
        zones=self.client.get('/api/v1/fishing-zones/?month=2027-01',**self.auth(self.user)).json()['zones']
        self.assertIn(created['id'],[z['id'] for z in zones])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/map/?month=2027-01').context['fishing_data']['zones'],zones)
        # A legacy month-only edit within the same month must preserve the exact day.
        body.pop('date');body['month']='2027-01';body['version']=created['version']
        response=self.client.post(f"/api/v1/fishing-zones/{created['id']}/",json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.json()['zone']['date'],'2027-01-17')
        self.assertEqual(response.json()['zone']['published_at'],created['published_at'])

    def test_publication_time_is_recorded_on_first_activation_and_retained(self):
        body=self.payload();body.update(date='2027-02-28',active=False,published_at='2000-01-01T00:00:00Z')
        response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.status_code,200,response.content)
        zone=FishingZone.objects.get(pk=response.json()['zone']['id'])
        self.assertIsNone(zone.published_at)
        self.client.force_login(self.admin)
        self.assertIn(str(zone.pk),[z['id'] for z in self.client.get('/map/?month=2027-02').context['fishing_data']['zones']])
        self.client.force_login(self.user)
        self.assertNotIn(str(zone.pk),[z['id'] for z in self.client.get('/map/?month=2027-02').context['fishing_data']['zones']])
        zone.active=True;zone.save();published=zone.published_at
        self.assertIsNotNone(published)
        zone.title='Updated title';zone.save()
        zone.active=False;zone.save();zone.active=True;zone.save();zone.refresh_from_db()
        self.assertEqual(zone.published_at,published)
        old=FishingZone.objects.filter(source_id__isnull=False).first()
        old.save();self.assertIsNone(old.published_at)

    def test_invalid_exact_dates_are_rejected(self):
        for value in ['2027-02-29','2027-01','2027-W01-1','1999-12-31','2101-01-01',None,20270117]:
            body=self.payload();body['date']=value
            response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
            self.assertEqual(response.status_code,400,(value,response.content))

    def test_django_admin_saves_an_exact_date_and_shows_field_errors(self):
        zone=FishingZone.objects.filter(date='2026-11-01').first()
        self.client.force_login(self.admin)
        path='/admin/aquawatch_app/fishingzone/add/'
        data={'title':'Exact date from admin','date':'2027-03-19','latitude':zone.latitude,
              'longitude':zone.longitude,'boundary':json.dumps(zone.boundary),'active':'on','_save':'Save'}
        response=self.client.post(path,data)
        self.assertEqual(response.status_code,302,response.content)
        created=FishingZone.objects.get(title=data['title'])
        self.assertEqual(created.date,date(2027,3,19))
        self.assertIsNotNone(created.published_at)
        data['date']='not-a-date'
        self.assertEqual(self.client.post(path,data).status_code,200)
        data['date']='2027-03-19';data['boundary']=json.dumps([
            {'lat':14.394717564146315,'lng':120.82617223262787},
            {'lat':14.395039716406593,'lng':120.82710564136507},
            {'lat':14.394364235326302,'lng':120.82799613475801},
            {'lat':14.39406286618496,'lng':120.82693397998811}])
        response=self.client.post(path,data)
        self.assertEqual(response.status_code,200)
        self.assertIn('boundary',response.context['adminform'].form.errors)
        self.assertContains(response,'Boundary point 1')
        self.assertContains(response,'admin-zone-map')
        self.assertContains(response,'Center pin in boundary')

    def test_yearly_zones_appear_in_future_novembers_without_duplicate_records(self):
        before=FishingZone.objects.count()
        original=self.client.get('/api/v1/fishing-zones/?month=2026-11',**self.auth(self.user)).json()['zones']
        self.assertEqual(len(original),10)
        for year in (2027,2028,2030,2100):
            response=self.client.get(f'/api/v1/fishing-zones/?month={year}-11',**self.auth(self.user))
            zones=response.json()['zones']
            self.assertEqual({z['id'] for z in zones},{z['id'] for z in original})
            self.assertTrue(all(z['occurrence_date']==f'{year}-11-01' for z in zones))
            self.assertTrue(all(z['date']=='2026-11-01' and z['repeats_annually'] for z in zones))
            self.client.force_login(self.user)
            web=self.client.get(f'/map/?month={year}-11')
            self.assertEqual(web.context['fishing_data']['zones'],zones)
            self.assertContains(web,'Choose month and year')
        self.assertEqual(FishingZone.objects.count(),before)
        self.assertEqual(self.client.get('/api/v1/fishing-zones/?month=2025-11',**self.auth(self.user)).json()['zones'],[])

    def test_yearly_opt_out_and_drafts_are_respected_across_years(self):
        body=self.payload();body.update(date='2026-11-17',repeats_annually=False)
        response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.status_code,200,response.content)
        zone=FishingZone.objects.get(pk=response.json()['zone']['id'])
        self.assertFalse(response.json()['zone']['repeats_annually'])
        def ids(period,user):
            return [z['id'] for z in self.client.get(f'/api/v1/fishing-zones/?month={period}',**self.auth(user)).json()['zones']]
        self.assertIn(str(zone.pk),ids('2026-11',self.user))
        self.assertNotIn(str(zone.pk),ids('2027-11',self.user))
        zone.repeats_annually=True;zone.save()
        self.assertIn(str(zone.pk),ids('2027-11',self.user))
        zone.active=False;zone.save()
        self.assertNotIn(str(zone.pk),ids('2027-11',self.user))
        self.assertIn(str(zone.pk),ids('2027-11',self.admin))
        body['repeats_annually']='true'
        response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.status_code,400)

    def test_editing_from_next_year_preserves_original_date_and_publication(self):
        body=self.payload();body.update(date='2026-11-17',repeats_annually=True)
        response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
        created=response.json()['zone']
        body.pop('date');body.update(month='2027-11',version=created['version'],title='Next-year edit')
        response=self.client.post(f"/api/v1/fishing-zones/{created['id']}/",json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.status_code,200,response.content)
        edited=response.json()['zone']
        self.assertEqual(edited['date'],'2026-11-17')
        self.assertEqual(edited['published_at'],created['published_at'])
        future=self.client.get('/api/v1/fishing-zones/?month=2027-11',**self.auth(self.user)).json()['zones']
        self.assertEqual(next(z for z in future if z['id']==created['id'])['occurrence_date'],'2027-11-17')

    def test_leap_day_recurrence_uses_february_28_in_non_leap_years(self):
        body=self.payload();body.update(date='2028-02-29',repeats_annually=True)
        response=self.client.post('/api/v1/fishing-zones/',json.dumps(body),content_type='application/json',**self.auth(self.admin))
        self.assertEqual(response.status_code,200,response.content)
        identifier=response.json()['zone']['id']
        for year,day in ((2029,28),(2032,29)):
            zones=self.client.get(f'/api/v1/fishing-zones/?month={year}-02',**self.auth(self.user)).json()['zones']
            zone=next(z for z in zones if z['id']==identifier)
            self.assertEqual(zone['date'],'2028-02-29')
            self.assertEqual(zone['occurrence_date'],f'{year}-02-{day}')
