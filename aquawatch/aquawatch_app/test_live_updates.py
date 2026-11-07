import json
import uuid
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from .api import issue_token
from .models import Device

class LiveUpdateTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('live-owner',password='Live-test-123!')
        self.other=User.objects.create_user('live-other',password='Live-test-123!')
        self.admin=User.objects.create_superuser('live-admin','live-admin@example.invalid','Live-test-123!')
        self.headers={'HTTP_AUTHORIZATION':'Bearer '+issue_token(self.user)['token']}
        self.client.force_login(self.user)

    def revision(self):return self.client.get('/sync-status/').json()['revision']
    def event(self,kind,data):
        response=self.client.post('/api/v1/sync/',json.dumps({'events':[{'id':str(uuid.uuid4()),'kind':kind,'data':data}]}),
                                  content_type='application/json',**self.headers)
        self.assertEqual(response.status_code,200,response.content)
        return response.json()['snapshot']

    def test_every_shared_mobile_mutation_changes_the_web_revision(self):
        now=int(timezone.now().timestamp()*1000)
        events=[('device.upsert',{'id':'live-phone','name':'Initial tracker','serial':'LIVE-01'}),
                ('device.upsert',{'id':'live-phone','name':'Renamed tracker','serial':'LIVE-01'}),
                ('profile.update',{'first_name':'Maria','last_name':'Santos','phone':'09171234567'}),
                ('area.update',{'latitude':14.41,'longitude':120.78,'label':'Amaya Watch'}),
                ('report.create',{'id':'live-report','type':'Incident','location':'Amaya coast','severity':'High','created_at':now}),
                ('reading.create',{'device_id':'live-phone','received_at':now,'latitude':14.41,'longitude':120.78,'alert_type':'SOS','is_distress':True}),
                ('alert.dismiss',{'alert_id':f'live-phone-{now}'})]
        for kind,data in events:
            before=self.revision();self.event(kind,data)
            self.assertNotEqual(before,self.revision(),kind)
        self.assertEqual(Device.objects.get().name,'Renamed tracker')
        self.assertEqual(self.revision(),self.revision(),'Unchanged data must not repeatedly reload the page')

    def test_foreign_account_writes_do_not_change_a_regular_users_revision(self):
        before=self.revision()
        Device.objects.create(user=self.other,name='Private tracker',serial='PRIVATE')
        self.assertEqual(before,self.revision())
        self.client.force_login(self.admin);before=self.revision()
        Device.objects.filter(user=self.other).update(name='Updated private tracker')
        self.assertNotEqual(before,self.revision())

    def test_read_only_device_lists_have_a_baseline_and_forms_are_preserved(self):
        response=self.client.get('/devices/')
        self.assertContains(response,'id="live-revision"')
        self.assertContains(response,'live-updates.')
        self.assertEqual(response.context['aqua_live_revision'],self.revision())
        self.assertNotContains(self.client.get('/profile/'),'id="live-revision"')
        self.assertNotContains(self.client.get('/map/?month=2026-11'),'id="live-revision"')
