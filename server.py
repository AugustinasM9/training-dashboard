#!/usr/bin/env python3
"""
Augustinas Training Dashboard — Cloud Ready + Password Protected
"""
import http.server, urllib.request, urllib.error, urllib.parse
import base64, json, os, sys, secrets, time

ATHLETE_ID    = os.environ.get('ATHLETE_ID',    'i222534')
API_KEY       = os.environ.get('ICU_API_KEY',   '6rrza8s3bs7l08hjbvpiqy3a9')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')
PASSWORD      = os.environ.get('DASHBOARD_PASSWORD', 'trainer2026')
AUTH          = base64.b64encode(f'API_KEY:{API_KEY}'.encode()).decode()
PORT          = int(os.environ.get('PORT', 8080))
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
HTML_PATH     = os.path.join(SCRIPT_DIR, 'dashboard.html')

# In-memory sessions: token -> expiry timestamp
SESSIONS = {}
SESSION_TTL = 7 * 24 * 3600  # 7 days

def clean_sessions():
    now = time.time()
    expired = [t for t, exp in SESSIONS.items() if now > exp]
    for t in expired:
        del SESSIONS[t]

def valid_session(token):
    clean_sessions()
    return token and token in SESSIONS and time.time() < SESSIONS[token]

LOGIN_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Training Dashboard — Login</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800&family=Barlow:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Barlow',sans-serif;background:#111114;color:#e8e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{background:#18181c;border:1px solid #2a2a35;border-radius:12px;padding:40px 36px;width:100%;max-width:360px}
.logo{font-family:'Barlow Condensed',sans-serif;font-size:28px;font-weight:800;color:#fff;letter-spacing:.06em;text-align:center;margin-bottom:6px}
.logo span{color:#E01A22}
.sub{text-align:center;font-size:12px;color:#505060;margin-bottom:32px;letter-spacing:.04em;text-transform:uppercase}
label{display:block;font-size:11px;font-weight:700;color:#9090a0;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}
input{width:100%;background:#111114;border:1px solid #2a2a35;border-radius:6px;padding:12px 14px;font-size:14px;color:#e8e8f0;font-family:'Barlow',sans-serif;outline:none;margin-bottom:20px;transition:border-color .15s}
input:focus{border-color:#E01A22}
button{width:100%;background:#E01A22;border:none;color:#fff;padding:13px;border-radius:6px;font-size:14px;font-weight:700;cursor:pointer;font-family:'Barlow',sans-serif;letter-spacing:.06em;text-transform:uppercase;transition:background .15s}
button:hover{background:#c01218}
.err{color:#E01A22;font-size:12px;text-align:center;margin-top:12px;display:none}
</style>
</head>
<body>
<div class="box">
  <div class="logo">TRAIN<span>ER</span></div>
  <div class="sub">Personal Training Dashboard</div>
  <label>Password</label>
  <input type="password" id="pw" placeholder="Enter password" onkeydown="if(event.key==='Enter')login()">
  <button onclick="login()">Sign In</button>
  <div class="err" id="err">Incorrect password</div>
</div>
<script>
async function login(){
  const pw=document.getElementById('pw').value;
  const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
  if(r.ok){const d=await r.json();localStorage.setItem('dash_token',d.token);location.reload();}
  else{document.getElementById('err').style.display='block';}
}
</script>
</body>
</html>'''

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f'  {self.command} {self.path}')

    def get_token(self):
        # Check Authorization header first
        auth = self.headers.get('X-Dash-Token', '')
        if auth:
            return auth
        # Check cookie
        cookie = self.headers.get('Cookie', '')
        for part in cookie.split(';'):
            part = part.strip()
            if part.startswith('dash_token='):
                return part[len('dash_token='):]
        return ''

    def send_json(self, code, data):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html, code=200):
        body = html.encode()
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def proxy_icu(self, method, body=None):
        parsed   = urllib.parse.urlparse(self.path)
        api_path = parsed.path[4:]
        qs       = ('?' + parsed.query) if parsed.query else ''
        url      = f'https://intervals.icu/api/v1/athlete/{ATHLETE_ID}{api_path}{qs}'
        req      = urllib.request.Request(url, data=body, method=method)
        req.add_header('Authorization', f'Basic {AUTH}')
        req.add_header('Accept', 'application/json')
        req.add_header('Content-Type', 'application/json')
        req.add_header('User-Agent', 'Mozilla/5.0')
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                self.send_json(r.status, r.read())
        except urllib.error.HTTPError as e:
            self.send_json(e.code, e.read())
        except Exception as e:
            self.send_json(500, {'error': str(e)})

    def proxy_claude(self, body):
        if not ANTHROPIC_KEY:
            self.send_json(500, {'error': 'ANTHROPIC_KEY not set'})
            return
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body, method='POST'
        )
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

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,X-Dash-Token')
        self.end_headers()

    def do_GET(self):
        # Login page — no auth needed
        if self.path == '/login':
            self.send_html(LOGIN_HTML)
            return

        # API calls — check auth
        if self.path.startswith('/api/'):
            if not valid_session(self.get_token()):
                self.send_json(401, {'error': 'Unauthorized'})
                return
            self.proxy_icu('GET')
            return

        # Dashboard — check auth, redirect to login if not
        if not valid_session(self.get_token()):
            self.send_html(LOGIN_HTML)
            return

        try:
            with open(HTML_PATH, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'dashboard.html not found')

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n) if n else b''

        # Login endpoint — no auth needed
        if self.path == '/login':
            try:
                data = json.loads(body)
                if data.get('password') == PASSWORD:
                    token = secrets.token_hex(32)
                    SESSIONS[token] = time.time() + SESSION_TTL
                    self.send_json(200, {'token': token})
                else:
                    self.send_json(401, {'error': 'Wrong password'})
            except Exception:
                self.send_json(400, {'error': 'Bad request'})
            return

        # Logout
        if self.path == '/logout':
            token = self.get_token()
            if token in SESSIONS:
                del SESSIONS[token]
            self.send_json(200, {'ok': True})
            return

        # All other POST endpoints need auth
        if not valid_session(self.get_token()):
            self.send_json(401, {'error': 'Unauthorized'})
            return

        if self.path == '/claude':
            self.proxy_claude(body)
        elif self.path.startswith('/api/'):
            self.proxy_icu('POST', body)

    def do_PUT(self):
        if not valid_session(self.get_token()):
            self.send_json(401, {'error': 'Unauthorized'})
            return
        if self.path.startswith('/api/'):
            n = int(self.headers.get('Content-Length', 0))
            self.proxy_icu('PUT', self.rfile.read(n) if n else b'')

if __name__ == '__main__':
    if not os.path.exists(HTML_PATH):
        print(f'ERROR: dashboard.html not found in {SCRIPT_DIR}')
        sys.exit(1)
    print(f'Dashboard running at http://localhost:{PORT}')
    print(f'Password protection: {"ON" if PASSWORD else "OFF (set DASHBOARD_PASSWORD env var)"}')
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
