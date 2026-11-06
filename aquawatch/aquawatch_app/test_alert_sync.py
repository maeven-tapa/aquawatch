import json
import uuid
from django.contrib.auth.models import User
from django.test import TestCase,Client
from django.utils import timezone
from .api import issue_token
from .models import Alert,AlertDismissal,Device,DeviceReading
from .alert_services import active_alerts

class AlertSyncTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner=User.objects.create_user('alert-owner',password='Alert-fixture-123!')
        cls.other=User.objects.create_user('alert-other',password='Alert-fixture-123!')
        cls.admin=User.objects.create_superuser('alert-admin','admin-alert@example.invalid','Alert-fixture-123!')
        cls.device=Device.objects.create(user=cls.owner,mobile_id='phone-1',name='Coastal boat',serial='AL-01')

    def setUp(self):
        self.auth={'HTTP_AUTHORIZATION':'Bearer '+issue_token(self.owner)['token']}
        self.received=int(timezone.now().timestamp()*1000)
        self.key=f'phone-1-{self.received}'
        self.data={'device_id':'phone-1','received_at':self.received,'latitude':14.41,'longitude':120.78,
                   'alert_type':'SOS','is_distress':True}

    def sync(self,kind=None,data=None,event_id=None,auth=None):
        events=[] if kind is None else [{'id':event_id or str(uuid.uuid4()),'kind':kind,'data':data}]
        return self.client.post('/api/v1/sync/',json.dumps({'events':events}),content_type='application/json',**(auth or self.auth))

    def test_real_phone_alert_appears_on_web_and_mobile_with_shared_identity(self):
        response=self.sync('reading.create',self.data)
        self.assertEqual(response.status_code,200,response.content)
        alert=response.json()['snapshot']['alerts'][0]
        self.assertEqual(alert['id'],self.key);self.assertEqual(alert['device_name'],'Coastal boat')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get('/alerts/'),'SOS')
        self.assertEqual(self.client.get('/alerts/feed/').json()['alerts'][0]['id'],self.key)
        self.assertEqual(DeviceReading.objects.count(),1)

    def test_backfill_and_live_upload_retries_do_not_duplicate_alerts(self):
        for _ in range(2): self.assertEqual(self.sync('alert.create',self.data).status_code,200)
        self.assertEqual(Alert.objects.count(),1);self.assertEqual(DeviceReading.objects.count(),0)
        self.assertEqual(self.sync('reading.create',self.data).status_code,200)
        self.assertEqual(Alert.objects.count(),1);self.assertEqual(DeviceReading.objects.count(),1)

    def test_mobile_dismissal_hides_alert_on_both_platforms_but_keeps_history(self):
        self.sync('reading.create',self.data)
        response=self.sync('alert.dismiss',{'alert_id':self.key})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['snapshot']['alerts'],[])
        self.assertEqual(response.json()['snapshot']['dismissed_alert_ids'],[self.key])
        self.client.force_login(self.owner)
        self.assertContains(self.client.get('/alerts/'),'No active alerts')
        self.assertEqual(Alert.objects.count(),1);self.assertEqual(DeviceReading.objects.count(),1)
        self.assertEqual(active_alerts(self.owner).count(),0)

    def test_offline_dismissal_before_alert_upload_does_not_resurrect(self):
        self.assertEqual(self.sync('alert.dismiss',{'alert_id':self.key}).status_code,200)
        self.sync('alert.create',self.data)
        self.sync('reading.create',self.data)
        self.assertEqual(self.sync().json()['snapshot']['alerts'],[])
        self.assertEqual(Alert.objects.count(),1)
        self.assertEqual(AlertDismissal.objects.count(),1)

    def test_web_dismissal_is_returned_to_phone_and_is_idempotent(self):
        self.sync('reading.create',self.data)
        alert=Alert.objects.get()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f'/alerts/{alert.pk}/dismiss/').status_code,405)
        for _ in range(2):self.assertEqual(self.client.post(f'/alerts/{alert.pk}/dismiss/').status_code,302)
        self.assertEqual(self.sync('alert.dismiss',{'alert_id':self.key}).status_code,200)
        self.assertEqual(self.sync().json()['snapshot']['dismissed_alert_ids'],[self.key])
        self.assertEqual(AlertDismissal.objects.count(),1)

    def test_regular_user_cannot_dismiss_another_accounts_alert(self):
        alert=Alert.objects.create(user=self.other,type='Private SOS',location='Bay',time='Now',severity='High')
        response=self.sync('alert.dismiss',{'alert_id':f'web-{alert.pk}'})
        self.assertGreaterEqual(response.status_code,400)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(f'/alerts/{alert.pk}/dismiss/').status_code,404)
        self.assertEqual(AlertDismissal.objects.count(),0)
        self.assertEqual(active_alerts(self.other).count(),1)

    def test_source_keys_are_scoped_to_the_account(self):
        self.sync('alert.create',self.data)
        Alert.objects.create(user=self.other,source_id=self.key,type='Other SOS',location='Bay',time='Now',severity='High')
        self.sync('alert.dismiss',{'alert_id':self.key})
        self.assertEqual(active_alerts(self.owner).count(),0)
        self.assertEqual(active_alerts(self.other).count(),1)

    def test_dismissal_is_csrf_protected_and_admin_can_dismiss_for_owner(self):
        self.sync('alert.create',self.data);alert=Alert.objects.get()
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.owner)
        self.assertEqual(csrf.post(f'/alerts/{alert.pk}/dismiss/').status_code,403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/alerts/'),'SOS')
        self.assertEqual(self.client.post(f'/alerts/{alert.pk}/dismiss/').status_code,302)
        self.assertEqual(self.sync().json()['snapshot']['alerts'],[])

    def test_native_web_alerts_have_a_stable_dismissal_key(self):
        alert=Alert.objects.create(user=self.owner,type='Weather',location='Manila Bay',time='Now',severity='High')
        self.assertEqual(self.sync('alert.dismiss',{'alert_id':f'web-{alert.pk}'}).status_code,200)
        self.assertEqual(self.sync().json()['snapshot']['alerts'],[])
        self.assertEqual(Alert.objects.count(),1)

    def test_distress_reading_without_alert_type_still_creates_an_alert(self):
        data=dict(self.data,alert_type='')
        response=self.sync('reading.create',data)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['snapshot']['alerts'][0]['type'],'Distress')
