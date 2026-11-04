"""Client for the existing MR-Mem AML Search service; no ranking reimplementation."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class MrMemSearch:
    def __init__(self, url, token_env=None):
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('MR-Mem URL must be a loopback HTTP service root')
        self.url = url.rstrip('/') + '/search'
        self.token_env = token_env

    def call(self, route, payload=None):
        if route not in ('health','add','search','admin/flush'):
            raise ValueError('unsupported MR-Mem route')
        headers = {'Content-Type':'application/json'}
        if self.token_env:
            token=os.environ.get(self.token_env)
            if not token: raise ValueError('MR-Mem service token unavailable')
            headers['Authorization']='Bearer '+token
        request=urllib.request.Request(self.url.removesuffix('/search')+'/'+route,
            data=None if payload is None else json.dumps(payload).encode(), headers=headers,
            method='GET' if payload is None else 'POST')
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            with opener.open(request,timeout=1900) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in (400,409,422): raise ValueError('MR-Mem rejected this request') from None
            if error.code in (401,403): raise PermissionError('MR-Mem authentication failed') from None
            raise OSError('MR-Mem service unavailable') from None
        except (OSError,ValueError):
            raise OSError('MR-Mem service request failed') from None

    def search(self, user_id, query):
        headers = {'Content-Type': 'application/json'}
        if self.token_env:
            token = os.environ.get(self.token_env)
            if not token:
                raise ValueError('MR-Mem service token environment variable is missing')
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(self.url, data=json.dumps(
            {'user_id':user_id, 'query':query, 'top_k':100}).encode(), headers=headers, method='POST')
        try:
            # Bypass environment proxies for the explicitly local service; never follow redirects.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            with opener.open(request, timeout=1900) as response:
                data = json.load(response)
        except (OSError, ValueError):
            raise OSError('MR-Mem search service unavailable') from None
        if not isinstance(data, dict) or not isinstance(data.get('data'), list):
            raise OSError('MR-Mem search response invalid')
        for item in data['data']:
            if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                    or not isinstance(item.get('content'), str)):
                raise OSError('MR-Mem search response invalid')
        return data['data'][:100]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
