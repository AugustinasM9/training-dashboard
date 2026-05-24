#!/usr/bin/env python3
"""Training Dashboard Server - Clean & Working"""
import http.server, urllib.request, urllib.error, urllib.parse, json, os, secrets, time, base64, sys, traceback

ATHLETE_ID = os.environ.get('ATHLETE_ID', 'i222534')
API_KEY = os.environ.get('ICU_API_KEY', '6rrza8s3bs7l08hjbvpiqy3a9')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')
PASSWORD = os.environ.get('DASHBOARD_PASSWORD', 'trainer2026')
PORT = int(os.environ.get('PORT', 8080))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(SCRIPT_DIR, 'dashboard.html')

AUTH_HEADER = base64.b64encode(f'API_KEY:{API_KEY}'.encode()).decode()
SESSIONS = {}

def proxy_icu(api_path, query, method='GET', body=None):
    """Proxy a request to intervals.icu API"""
    qs = ('?' + query) if query else ''
    url = f'https://intervals.icu/api/v1/athlete/{ATHLETE_ID}{api_path}{qs}'
    print(f'  → ICU: {method} {url}', flush=True)
    
    req = urllib.request.Request(url, method=method)
    req.add_header('Authorization', f'Basic {AUTH_HEADER}')
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    req.add_header('Accept-Language', 'en-US,en;q=0.9')
    req.add_header('Accept-Encoding', 'gzip, deflate, br')
    req.add_header('Referer', 'https://intervals.icu/')
    req.add_header('Origin', 'https://intervals.icu')
    if body:
        req.data = body
        req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            # Handle gzip if needed
            if r.headers.get('Content-Encoding') == 'gzip':
                import gzip
                raw = gzip.decompress(raw)
            print(f'  ← ICU: {r.status} ({len(raw)} bytes)', flush=True)
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                # Response wasn't JSON - return as text
                return r.status, {'raw': raw.decode('utf-8', errors='replace')[:500]}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:500]
        print(f'  ✗ ICU HTTP {e.code}: {body}', flush=True)
        return e.code, {'error': f'ICU {e.code}', 'detail': body}
    except Exception as e:
        print(f'  ✗ ICU Exception: {e}', flush=True)
        traceback.print_exc()
        return 500, {'error': str(e)}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f'  {self.command} {self.path}', flush=True)
    
    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        self.end_headers()
    
    def get_token(self):
        auth = self.headers.get('Authorization', '')
        return auth[7:] if auth.startswith('Bearer ') else ''
    
    def check_auth(self):
        token = self.get_token()
        if token in SESSIONS and time.time() < SESSIONS[token]:
            return True
        self.send_json(401, {'error': 'Unauthorized'})
        return False
    
    def do_GET(self):
        if self.path.startswith('/api/'):
            if not self.check_auth():
                return
            parsed = urllib.parse.urlparse(self.path)
            api_path = parsed.path[4:]  # /api/wellness -> /wellness
            code, data = proxy_icu(api_path, parsed.query, 'GET')
            self.send_json(code, data)
            return
        
        # Serve dashboard
        try:
            with open(HTML_FILE, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'dashboard.html not found')
    
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        raw_body = self.rfile.read(n) if n else b''
        
        # Login
        if self.path == '/login':
            try:
                data = json.loads(raw_body)
                pwd = str(data.get('password', '')).strip()
                if pwd == PASSWORD.strip():
                    token = secrets.token_hex(32)
                    SESSIONS[token] = time.time() + (7 * 24 * 3600)
                    print(f'  ✓ Login OK ({len(SESSIONS)} active sessions)', flush=True)
                    self.send_json(200, {'token': token})
                else:
                    print(f'  ✗ Login failed', flush=True)
                    self.send_json(401, {'error': 'Wrong password'})
            except Exception as e:
                print(f'  ✗ Login exception: {e}', flush=True)
                self.send_json(400, {'error': str(e)})
            return
        
        # API proxy POST
        if self.path.startswith('/api/'):
            if not self.check_auth():
                return
            parsed = urllib.parse.urlparse(self.path)
            api_path = parsed.path[4:]
            code, data = proxy_icu(api_path, parsed.query, 'POST', raw_body)
            self.send_json(code, data)
            return
        
        # Claude proxy
        if self.path == '/claude':
            if not self.check_auth():
                return
            if not ANTHROPIC_KEY:
                self.send_json(500, {'error': 'ANTHROPIC_KEY not set'})
                return
            try:
                req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=raw_body, method='POST')
                req.add_header('x-api-key', ANTHROPIC_KEY)
                req.add_header('anthropic-version', '2023-06-01')
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=60) as r:
                    self.send_json(200, json.loads(r.read()))
            except urllib.error.HTTPError as e:
                self.send_json(e.code, json.loads(e.read()))
            except Exception as e:
                self.send_json(500, {'error': str(e)})
            return
        
        self.send_json(404, {'error': 'Not found'})


if __name__ == '__main__':
    if not os.path.exists(HTML_FILE):
        print(f'ERROR: dashboard.html not found at {HTML_FILE}', flush=True)
        sys.exit(1)
    print(f'', flush=True)
    print(f'═══════════════════════════════════════════', flush=True)
    print(f'  Training Dashboard Server', flush=True)
    print(f'  Port:        {PORT}', flush=True)
    print(f'  Athlete ID:  {ATHLETE_ID}', flush=True)
    print(f'  Password:    {PASSWORD}', flush=True)
    print(f'  Anthropic:   {"set" if ANTHROPIC_KEY else "NOT SET"}', flush=True)
    print(f'═══════════════════════════════════════════', flush=True)
    print(f'', flush=True)
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Stopped.', flush=True)
