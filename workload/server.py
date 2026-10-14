"""An intentionally small workload: a real HTTP health gate and release response."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.environ.get("APP_VERSION", "v1")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        healthy = VERSION != "bad-health"
        self.send_response(503 if self.path == "/health" and not healthy else 200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"release": VERSION, "healthy": healthy, "message": "Hello from a real Launchpad workload"}).encode())


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
