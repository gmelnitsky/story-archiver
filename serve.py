#!/usr/bin/env python3
"""Serve the archive at http://localhost:8123. Local only — binds to 127.0.0.1."""

import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8123

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))

with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
    url = f"http://localhost:{PORT}/site/"
    print(f"the journalist archive → {url}\nCtrl-C to stop.")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
