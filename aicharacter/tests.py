from django.test import TestCase, Client
from django.urls import reverse

class AICharacterTests(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_index_page(self):
        response = self.client.get(reverse('aicharacter:index'))
        self.assertEqual(response.status_code, 200)
    
    def test_get_response(self):
        response = self.client.post(
            reverse('aicharacter:get_response'),
            {'user_input': 'Hello'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('response', response.json()) 