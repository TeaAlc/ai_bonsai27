#!/usr/bin/env python3
"""Mini server: GET serves game dir, POST /shot?name=X saves PNG (base64 body),
POST /dbg?name=X saves raw body text for debug."""
import os, sys, base64, time, urllib.parse, http.server

os.chdir('/home/pi/develop/game')

TINY_PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='

class H(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def send_response(self, code, message=None):
        super().send_response(code, message)
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')

    def do_GET(self):
        if self.path.startswith('/img?hold='):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try: t = float(q.get('hold', ['1'])[0])
            except: t = 1.0
            time.sleep(t)
            self.send_response(200); self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', '31'); self.end_headers()
            self.wfile.write(base64.b64decode(TINY_PNG)); return
        if self.path.startswith('/dbg'):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = (q.get('name') or ['shot'])[0]
            with open('/tmp/dbg_%s.txt' % name, 'a', 'wb') as f:
                f.write(self.path.encode())
            self.send_response(200); self.end_headers(); return
        http.server.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = (q.get('name') or ['shot'])[0]
        n = int(self.headers.get('Content-Length', 0) or 0)
        data = self.rfile.read(n)
        fn = None
        if self.path.startswith('/dbg'):
            fn = '/tmp/dbg_%s.txt' % name
        else:  # /shot
            try:
                data = base64.b64decode(data)
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode())
                return
            fn = '/tmp/shot_%s.png' % name
        with open(fn, 'wb') as f:
            f.write(data)
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(b'ok:' + fn)

    def log_message(self, *a):
        print(*a, file=sys.stderr, flush=True)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), H)
    print('serving http://127.0.0.1:%d' % port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
