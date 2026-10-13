#!/usr/bin/env python3
# ==============================================================================
# TVDecoder OS - Natywny Serwer Aplikacji i Mostka API Pilota
# ==============================================================================

import os
import sys
import json
import time
import queue
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

APP_DIR = os.path.dirname(os.path.abspath(__file__))
event_subscribers = []
event_subscribers_lock = threading.Lock()

class DecoderHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=APP_DIR, **kwargs)

    def log_message(self, format, *args):
        # Ciche logowanie dla wydajności
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Strona główna dekodera
        if path == "/" or path == "/index.html":
            self.path = "/dekoder_aurora_ui.html"
            return super().do_GET()

        # 2. Endpoint API pilota: /api/remote?key=...
        if path == "/api/remote":
            query = parse_qs(parsed.query)
            key = query.get("key", [None])[0]
            if key:
                self.broadcast_key(key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        # 3. Server-Sent Events dla natychmiastowej transmisji komend pilota do UI
        if path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            q = queue.Queue(maxsize=50)
            with event_subscribers_lock:
                event_subscribers.append(q)

            try:
                # Wyślij powitalne zdarzenie
                self.wfile.write(b"data: {\"type\":\"connected\"}\n\n")
                self.wfile.flush()

                while True:
                    try:
                        msg = q.get(timeout=25.0)
                        self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive heartbeat ping
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with event_subscribers_lock:
                    if q in event_subscribers:
                        event_subscribers.remove(q)
            return

        # 4. Standardowa obsługa plików statycznych (HTML, obrazy, json, hls)
        return super().do_GET()

    def broadcast_key(self, key):
        payload = json.dumps({"key": key})
        with event_subscribers_lock:
            for q in list(event_subscribers):
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    pass

def run_server(port=8080):
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, DecoderHTTPHandler)
    print(f"[TVDecoder] Serwer aplikacji działa pod adresem http://127.0.0.1:{port}", flush=True)
    httpd.serve_forever()

if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
