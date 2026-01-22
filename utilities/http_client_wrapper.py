from unittest.mock import Mock


class HttpClientWrapper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = Mock()
        self.session.headers = {}
        self._authenticated = False
        self._request_prepared = False
    
    def set_headers(self, headers):
        if not headers:
            raise ValueError("Headers cannot be empty")
        
        self.session.headers.update(headers)
        return self
    
    def authenticate(self, token):
        if self._authenticated:
            raise RuntimeError("Already authenticated")

        if 'User-Agent' not in self.session.headers:
            self._authenticated = False
            self._request_prepared = False
            return self

        self.session.prepare_request = Mock(return_value={'prepared': True, 'token': token})
        self._request_prepared = True
        self._authenticated = True
        return self
    
    def get(self, endpoint):
        if not self._authenticated:
            raise RuntimeError("Not authenticated")
        
        if not self._request_prepared:
            raise RuntimeError("Request not prepared")

        url = f"{self.base_url}/{endpoint}"
        return {
            'url': url,
            'status': 200,
            'headers': dict(self.session.headers),
            'data': {'result': 'success'}
        }
    
    def post(self, endpoint, data):
        if not self._authenticated:
            raise RuntimeError("Not authenticated")
        
        if not self._request_prepared:
            raise RuntimeError("Request not prepared")
        
        url = f"{self.base_url}/{endpoint}"
        return {
            'url': url,
            'status': 201,
            'headers': dict(self.session.headers),
            'data': data
        }
    
    def close(self):
        self.session = None
        self._authenticated = False
        self._request_prepared = False
