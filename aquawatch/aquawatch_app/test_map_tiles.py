from django.contrib.auth.models import User
from django.test import TestCase

class MapTilePolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('map-policy-test',password='Map-policy-test-123!')

    def test_public_pages_allow_origin_identification_without_exposing_cross_site_paths(self):
        response=self.client.get('/login/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Referrer-Policy'],'strict-origin-when-cross-origin')

    def test_map_response_retains_origin_referrer_policy(self):
        self.client.force_login(self.user)
        response=self.client.get('/map/?month=2026-11')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Referrer-Policy'],'strict-origin-when-cross-origin')
        self.assertEqual(len(response.context['fishing_data']['zones']),10)
