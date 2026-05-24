#!/usr/bin/env python3
import http.server, urllib.request, urllib.error, urllib.parse, json, os, secrets, time, base64

ATHLETE_ID = os.environ.get('ATHLETE_ID', 'i222534')
API_KEY = os.environ.get('ICU_API_KEY', '6rrza8s3bs7l08hjbvpiqy3a9')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')
PASSWORD = os.environ.get('DASHBOARD_PASSWORD', 'trainer2026')
PORT = int(os.environ.get('PORT', 8080))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(SCRIPT_DIR, 'dashboard.html')

AUTH_HEADER = base64.b64encode(f'API_KEY:{API_KEY}'.encode()).decode()
SESSIONS = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): print(f'  {self.command} {self.path}')
    def send_json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        self.end_headers()
    
    def get_token(self):
        auth = self.headers.get('Authorization', '')
        return auth.replace('Bearer ', '') if auth.startswith('Bearer ') else ''
    
    def do_GET(self):
        if self.path.startswith('/api/'):
            token = self.get_token()
            if token not in SESSIONS or time.time() > SESSIONS[token]:
                self.send_json(401, {'error': 'Unauthorized'})
                return
            parsed = urllib.parse.urlparse(self.path)
            api_path = parsed.path[4:]
            qs = ('?' + parsed.query) if parsed.query else ''
            url = f'https://intervals.icu/api/v1/athlete/{ATHLETE_ID}{api_path}{qs}'
            try:
                req = urllib.request.Request(url)
                req.add_header('Authorization', f'Basic {AUTH_HEADER}')
                with urllib.request.urlopen(req, timeout=15) as r:
                    self.send_json(200, json.loads(r.read()))
            except Exception as e:
                self.send_json(500, {'error': str(e)})
            return
        
        try:
            with open(HTML_FILE, 'r') as f:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(f.read().encode())
        except:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n)) if n else {}
        
        if self.path == '/login':
            pwd = body.get('password', '').strip()
            if pwd == PASSWORD.strip():
                token = secrets.token_hex(32)
                SESSIONS[token] = time.time() + (7*24*3600)
                self.send_json(200, {'token': token})
            else:
                self.send_json(401, {'error': 'Wrong password'})
            return
        
        if self.path.startswith('/api/'):
            token = self.get_token()
            if token not in SESSIONS or time.time() > SESSIONS[token]:
                self.send_json(401, {'error': 'Unauthorized'})
                return
            parsed = urllib.parse.urlparse(self.path)
            api_path = parsed.path[4:]
            qs = ('?' + parsed.query) if parsed.query else ''
            url = f'https://intervals.icu/api/v1/athlete/{ATHLETE_ID}{api_path}{qs}'
            try:
                req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST')
                req.add_header('Authorization', f'Basic {AUTH_HEADER}')
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=15) as r:
                    self.send_json(200, json.loads(r.read()))
            except Exception as e:
                self.send_json(500, {'error': str(e)})
            return
        
        if self.path == '/claude':
            token = self.get_token()
            if token not in SESSIONS or time.time() > SESSIONS[token]:
                self.send_json(401, {'error': 'Unauthorized'})
                return
            try:
                req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(body).encode())
                req.add_header('x-api-key', ANTHROPIC_KEY)
                req.add_header('anthropic-version', '2023-06-01')
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=60) as r:
                    self.send_json(200, json.loads(r.read()))
            except Exception as e:
                self.send_json(500, {'error': str(e)})

if __name__ == '__main__':
    print(f'\n✓ Dashboard running at http://localhost:{PORT}\n')
    http.server.HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
