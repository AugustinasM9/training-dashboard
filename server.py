#!/usr/bin/env python3
"""Training Dashboard Server - Clean & Simple"""
import http.server, urllib.request, urllib.error, urllib.parse
import base64, json, os, sys, secrets, time

ATHLETE_ID    = os.environ.get('ATHLETE_ID', 'i222534')
API_KEY       = os.environ.get('ICU_API_KEY', '6rrza8s3bs7l08hjbvpiqy3a9')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')
PASSWORD      = os.environ.get('DASHBOARD_PASSWORD', 'trainer2026')
AUTH          = base64.b64encode(f'API_KEY:{API_KEY}'.encode()).decode()
PORT          = int(os.environ.get('PORT', 8080))
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
HTML_PATH     = os.path.join(SCRIPT_DIR, 'dashboard.html')

SESSIONS = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f'  {self.command} {self.path}')

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        self.end_headers()

    def do_GET(self):
        # API calls
        if self.path.startswith('/api/'):
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                self.send_json(401, {'error': 'Unauthorized'})
                return
            token = auth[7:]
            if token not in SESSIONS or time.time() > SESSIONS[token]:
                self.send_json(401, {'error': 'Invalid token'})
                return
            # Proxy to intervals.icu
            parsed = urllib.parse.urlparse(self.path)
            api_path = parsed.path[4:]
            qs = ('?' + parsed.query) if parsed.query else ''
            url = f'https://intervals.icu/api/v1/athlete/{ATHLETE_ID}{api_path}{qs}'
            req = urllib.request.Request(url, method='GET')
            req.add_header('Authorization', f'Basic {AUTH}')
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    self.send_json(r.status, r.read())
            except urllib.error.HTTPError as e:
                self.send_json(e.code, e.read())
            except Exception as e:
                self.send_json(500, {'error': str(e)})
            return

        # Serve dashboard HTML for everything else
        try:
            with open(HTML_PATH, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'dashboard.html not found')

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n) if n else b''

        # Login endpoint
        if self.path == '/login':
            try:
                data = json.loads(body)
                pwd = str(data.get('password', '')).strip()
                if pwd == PASSWORD.strip():
                    token = secrets.token_hex(32)
                    SESSIONS[token] = time.time() + (7 * 24 * 3600)
                    print(f'  ✓ Login successful')
                    self.send_json(200, {'token': token})
                else:
                    print(f'  ✗ Login failed: wrong password')
                    self.send_json(401, {'error': 'Wrong password'})
            except Exception as e:
                self.send_json(400, {'error': str(e)})
            return

        # API calls
        if self.path.startswith('/api/'):
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                self.send_json(401, {'error': 'Unauthorized'})
                return
            token = auth[7:]
            if token not in SESSIONS or time.time() > SESSIONS[token]:
                self.send_json(401, {'error': 'Invalid token'})
                return
            # Proxy to intervals.icu
            parsed = urllib.parse.urlparse(self.path)
            api_path = parsed.path[4:]
            qs = ('?' + parsed.query) if parsed.query else ''
            url = f'https://intervals.icu/api/v1/athlete/{ATHLETE_ID}{api_path}{qs}'
            req = urllib.request.Request(url, data=body, method='POST')
            req.add_header('Authorization', f'Basic {AUTH}')
            req.add_header('Content-Type', 'application/json')
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    self.send_json(r.status, r.read())
            except urllib.error.HTTPError as e:
                self.send_json(e.code, e.read())
            except Exception as e:
                self.send_json(500, {'error': str(e)})
            return

        # Claude proxy
        if self.path == '/claude':
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                self.send_json(401, {'error': 'Unauthorized'})
                return
            token = auth[7:]
            if token not in SESSIONS or time.time() > SESSIONS[token]:
                self.send_json(401, {'error': 'Invalid token'})
                return
            if not ANTHROPIC_KEY:
                self.send_json(500, {'error': 'ANTHROPIC_KEY not set'})
                return
            req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body, method='POST')
            req.add_header('x-api-key', ANTHROPIC_KEY)
            req.add_header('anthropic-version', '2023-06-01')
            req.add_header('Content-Type', 'application/json')
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    self.send_json(r.status, r.read())
            except urllib.error.HTTPError as e:
                self.send_json(e.code, e.read())
            except Exception as e:
                self.send_json(500, {'error': str(e)})
            return

if __name__ == '__main__':
    if not os.path.exists(HTML_PATH):
        print(f'ERROR: dashboard.html not found')
        sys.exit(1)
    print(f'\n✓ Dashboard running at http://localhost:{PORT}')
    print(f'✓ Password: {PASSWORD}\n')
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
