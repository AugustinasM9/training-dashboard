#!/usr/bin/env python3
"""
Training Dashboard Server
- Proxies intervals.icu API
- Proxies Anthropic Claude API for AI Coach
- Bearer token authentication
"""

import os
import json
import gzip
import secrets
import base64
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = int(os.environ.get('PORT', 10000))
PASSWORD = os.environ.get('DASH_PASSWORD', 'trainer2026')
ICU_ID = os.environ.get('ICU_ID', 'i222534')
ICU_KEY = os.environ.get('ICU_KEY', '6rrza8s3bs7l08hjbvpiqy3a9')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

TOKENS = set()

def make_token():
    return secrets.token_urlsafe(32)

def check_auth(headers):
    auth = headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    return auth[7:] in TOKENS

def icu_auth():
    """intervals.icu Basic auth: username='API_KEY', password=<your_key>"""
    creds = f"API_KEY:{ICU_KEY}"
    return 'Basic ' + base64.b64encode(creds.encode()).decode()

def proxy_icu(path, query, method='GET', body=None):
    url = f"https://intervals.icu/api/v1/athlete/{ICU_ID}{path}"
    if query:
        url += '?' + query
    print(f"[ICU] {method} {url}")
    
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', icu_auth())
    req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    req.add_header('Accept', 'application/json, text/plain, */*')
    req.add_header('Accept-Language', 'en-US,en;q=0.9')
    req.add_header('Accept-Encoding', 'gzip, deflate')
    if method == 'POST':
        req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            # Always handle gzip if present
            if response.headers.get('Content-Encoding') == 'gzip':
                raw = gzip.decompress(raw)
            return 200, raw.decode('utf-8')
    except urllib.error.HTTPError as e:
        raw = e.read()
        # Decompress error body too if gzipped
        if e.headers.get('Content-Encoding') == 'gzip':
            try:
                raw = gzip.decompress(raw)
            except:
                pass
        body = raw.decode('utf-8', errors='replace')
        print(f"[ICU ERROR {e.code}] {body[:200]}")
        return e.code, body
    except Exception as e:
        print(f"[ICU EXCEPTION] {e}")
        return 500, json.dumps({'error': str(e)})

def proxy_claude(body_data):
    if not ANTHROPIC_KEY:
        return 500, json.dumps({'error': 'ANTHROPIC_API_KEY not configured on server. Add it in Render Environment Variables.'})
    
    print(f"[CLAUDE] POST messages, {len(body_data)} bytes")
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body_data)
    req.add_header('Content-Type', 'application/json')
    req.add_header('x-api-key', ANTHROPIC_KEY)
    req.add_header('anthropic-version', '2023-06-01')
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return 200, response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"[CLAUDE ERROR {e.code}] {body[:300]}")
        return e.code, body
    except Exception as e:
        print(f"[CLAUDE EXCEPTION] {e}")
        return 500, json.dumps({'error': str(e)})

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")
    
    def send_json(self, status, data):
        body = data.encode('utf-8') if isinstance(data, str) else json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
    
    def serve_file(self, path):
        try:
            with open(path, 'rb') as f:
                body = f.read()
            ext = path.split('.')[-1].lower()
            ctype = {'html': 'text/html', 'css': 'text/css', 'js': 'application/javascript', 
                     'json': 'application/json', 'png': 'image/png', 'svg': 'image/svg+xml'}.get(ext, 'application/octet-stream')
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/' or path == '/index.html':
            self.serve_file('dashboard.html')
            return
        
        if path.startswith('/api/'):
            if not check_auth(self.headers):
                self.send_json(401, {'error': 'Unauthorized'})
                return
            status, body = proxy_icu(path[4:], parsed.query)
            self.send_json(status, body)
            return
        
        if path.endswith(('.css', '.js', '.png', '.svg', '.ico')):
            self.serve_file(path.lstrip('/'))
            return
        
        self.send_response(404)
        self.end_headers()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body_raw = self.rfile.read(length) if length > 0 else b''
        
        if path == '/login':
            try:
                data = json.loads(body_raw)
                if data.get('password') == PASSWORD:
                    token = make_token()
                    TOKENS.add(token)
                    print(f"[AUTH] Login success, token: {token[:8]}...")
                    self.send_json(200, {'token': token})
                else:
                    self.send_json(401, {'error': 'Invalid password'})
            except Exception as e:
                self.send_json(400, {'error': str(e)})
            return
        
        if path == '/claude':
            if not check_auth(self.headers):
                self.send_json(401, {'error': 'Unauthorized'})
                return
            status, body = proxy_claude(body_raw)
            self.send_json(status, body)
            return
        
        if path.startswith('/api/'):
            if not check_auth(self.headers):
                self.send_json(401, {'error': 'Unauthorized'})
                return
            status, body = proxy_icu(path[4:], parsed.query, method='POST', body=body_raw)
            self.send_json(status, body)
            return
        
        self.send_response(404)
        self.end_headers()

if __name__ == '__main__':
    print(f"Training Dashboard starting on port {PORT}")
    print(f"   ICU_ID: {ICU_ID}")
    print(f"   ICU auth: API_KEY:{ICU_KEY[:6]}...")
    print(f"   ANTHROPIC_KEY: {'set' if ANTHROPIC_KEY else 'NOT SET (chat will not work)'}")
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
