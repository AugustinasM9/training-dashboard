#!/usr/bin/env python3
"""
Augustinas Training Dashboard
Run: python3 server.py
Open: http://localhost:8080
"""
import http.server, urllib.request, urllib.error, urllib.parse
import base64, json, os, sys

ATHLETE_ID   = 'i222534'
API_KEY      = '6rrza8s3bs7l08hjbvpiqy3a9'
ANTHROPIC_KEY = 'YOUR_ANTHROPIC_API_KEY_HERE'   # ← paste your key
AUTH         = base64.b64encode(f'API_KEY:{API_KEY}'.encode()).decode()
PORT         = 8080
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
HTML_PATH    = os.path.join(SCRIPT_DIR, 'dashboard.html')

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f'  {self.command} {self.path}')

    def send_json(self, code, data):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def proxy(self, method, body=None):
        parsed   = urllib.parse.urlparse(self.path)
        api_path = parsed.path[4:]
        qs       = ('?' + parsed.query) if parsed.query else ''
        url      = f'https://intervals.icu/api/v1/athlete/{ATHLETE_ID}{api_path}{qs}'
        req      = urllib.request.Request(url, data=body, method=method)
        req.add_header('Authorization', f'Basic {AUTH}')
        req.add_header('Accept', 'application/json')
        req.add_header('Content-Type', 'application/json')
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                self.send_json(r.status, r.read())
        except urllib.error.HTTPError as e:
            self.send_json(e.code, e.read())
        except Exception as e:
            self.send_json(500, {'error': str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/api/'):
            self.proxy('GET')
        else:
            with open(HTML_PATH, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(data)

    def do_POST(self):
        if self.path.startswith('/api/'):
            n = int(self.headers.get('Content-Length', 0))
            self.proxy('POST', self.rfile.read(n) if n else b'')
        elif self.path == '/claude':
            n = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(n) if n else b''
            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=body, method='POST'
            )
            req.add_header('x-api-key', ANTHROPIC_KEY)
            req.add_header('anthropic-version', '2023-06-01')
            req.add_header('Content-Type', 'application/json')
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    self.send_json(r.status, r.read())
            except urllib.error.HTTPError as e:
                self.send_json(e.code, e.read())
            except Exception as e:
                self.send_json(500, {'error': str(e)})

    def do_PUT(self):
        if self.path.startswith('/api/'):
            n = int(self.headers.get('Content-Length', 0))
            self.proxy('PUT', self.rfile.read(n) if n else b'')

if __name__ == '__main__':
    if not os.path.exists(HTML_PATH):
        print(f'ERROR: dashboard.html not found in {SCRIPT_DIR}')
        sys.exit(1)
    server = http.server.HTTPServer(('localhost', PORT), Handler)
    print(f'Dashboard running at http://localhost:{PORT}  |  Ctrl+C to stop')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
