"""Controlled local target. Every fifth request fails in degraded mode."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time

lock = threading.Lock()
count = 0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global count
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path != "/work":
            self.send_response(404)
            self.end_headers()
            return
        with lock:
            count += 1
            current = count
        degraded = os.getenv("MODE", "healthy") == "degraded"
        time.sleep(0.2 if degraded else 0.016)
        status = 503 if degraded and current % 5 == 0 else 200
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"status": status, "mode": os.getenv("MODE", "healthy")}).encode()
        )

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
