#!/usr/bin/env -S python3 -B
"""Regression checks for LAN API transport and the real vision CLI."""
import sys
sys.dont_write_bytecode = True
import json
import os
import socket
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
import api_http


class TransportTests(unittest.TestCase):
    def test_all_address_errors_are_preserved(self):
        endpoints = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', 8080)),
                     (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2001:db8::1', 8080, 0, 0))]
        sockets = [Mock(), Mock()]
        sockets[0].connect.side_effect = ConnectionRefusedError(111, 'Connection refused')
        sockets[1].connect.side_effect = OSError(101, 'Network is unreachable')
        with patch.object(socket, 'getaddrinfo', return_value=endpoints), \
                patch.object(socket, 'socket', side_effect=sockets):
            with self.assertRaises(OSError) as failure:
                api_http.connect(('mintai', 8080), 1)
        self.assertIn('Connection refused', str(failure.exception))
        self.assertIn('Network is unreachable', str(failure.exception))
        for connection in sockets:
            connection.close.assert_called_once()

    def test_fallback_address_succeeds(self):
        endpoints = [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('::1', 8080, 0, 0)),
                     (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 8080))]
        sockets = [Mock(), Mock()]
        sockets[0].connect.side_effect = OSError(101, 'Network is unreachable')
        with patch.object(socket, 'getaddrinfo', return_value=endpoints), \
                patch.object(socket, 'socket', side_effect=sockets):
            self.assertIs(api_http.connect(('host', 8080), 1), sockets[1])
        sockets[1].close.assert_not_called()

    def test_vision_cli_ignores_proxy_and_prints_json(self):
        captured = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"choices":[{"message":{"content":"Unicorns"}}]}')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            environment = dict(os.environ, http_proxy='http://127.0.0.1:1',
                               HTTP_PROXY='http://127.0.0.1:1', no_proxy='', NO_PROXY='')
            process = subprocess.run([str(Path(__file__).resolve().parents[1] / 'simple_request.sh'),
                                      f'localhost:{server.server_port}'], env=environment,
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn('\n  "choices"', process.stdout)
            self.assertEqual(json.loads(process.stdout)['choices'][0]['message']['content'], 'Unicorns')
            self.assertTrue(captured[0]['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
