from django.test import TestCase

from utilities.http_client_wrapper import HttpClientWrapper


class HttpClientWrapperTest(TestCase):

    def test_correct_sequence(self):
        client = HttpClientWrapper('https://api.example.com')
        
        client.set_headers({
            'User-Agent': 'TestClient/1.0',
            'Accept': 'application/json'
        })
        client.authenticate('secret-token-123')
        
        response = client.get('users')
        
        self.assertEqual(response['status'], 200)
        self.assertEqual(response['data']['result'], 'success')
    
    def test_authenticate_without_headers(self):
        client = HttpClientWrapper('https://api.example.com')

        client.authenticate('secret-token-123')

        with self.assertRaises(RuntimeError) as cm:
            client.get('users')
        
        self.assertIn('Not authenticated', str(cm.exception))
    
    def test_request_without_authentication(self):
        client = HttpClientWrapper('https://api.example.com')
        
        client.set_headers({
            'User-Agent': 'TestClient/1.0'
        })
        
        with self.assertRaises(RuntimeError) as cm:
            client.get('users')
        
        self.assertIn('Not authenticated', str(cm.exception))
    
    def test_post_request(self):
        client = HttpClientWrapper('https://api.example.com')
        
        client.set_headers({
            'User-Agent': 'TestClient/1.0',
            'Content-Type': 'application/json'
        })
        client.authenticate('secret-token-456')
        
        response = client.post('users', {'name': 'John', 'email': 'john@example.com'})
        
        self.assertEqual(response['status'], 201)
        self.assertEqual(response['data']['name'], 'John')
    
    def test_missing_user_agent(self):
        client = HttpClientWrapper('https://api.example.com')

        client.set_headers({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        client.authenticate('secret-token-789')

        response = client.get('users')
        
        self.assertEqual(response['status'], 200)
        self.assertEqual(response['data']['result'], 'success')
    
    def test_multiple_requests(self):
        client = HttpClientWrapper('https://api.example.com')
        
        client.set_headers({
            'User-Agent': 'TestClient/1.0'
        })
        client.authenticate('token-abc')
        
        response1 = client.get('users')
        response2 = client.get('posts')
        response3 = client.post('comments', {'text': 'Great!'})
        
        self.assertEqual(response1['status'], 200)
        self.assertEqual(response2['status'], 200)
        self.assertEqual(response3['status'], 201)
