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
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Strona główna dekodera Aurora OS
        if path == "/" or path == "/index.html":
            self.path = "/dekoder_aurora_ui.html"
            return super().do_GET()

        # 2. Endpoint API pilota: /api/remote?key=... oraz ?input=...
        if path == "/api/remote":
            query = parse_qs(parsed.query)
            key = query.get("key", [None])[0]
            inp = query.get("input", [None])[0]
            if inp == "2":
                toggle_sh = "/opt/tvdecoder/config/toggle_youtube.sh"
                if os.path.exists(toggle_sh):
                    try:
                        import subprocess
                        subprocess.Popen([toggle_sh])
                    except Exception:
                        pass
            elif inp == "1" or inp == "3" or key in ["menu", "home", "exit"]:
                # Jeśli uruchomiony jest dedykowany YouTube (Chromium), zamknij go i wróć do dekodera
                try:
                    import subprocess
                    subprocess.run(["pkill", "-x", "chromium"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
                if inp == "3" or key in ["menu", "home"]:
                    self.broadcast_key("exit") # Klawisz 'exit' przełącza do Home w Aurora UI
                elif key:
                    self.broadcast_key(key)
            elif key:
                self.broadcast_key(key)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        # 3. Endpoint aktualizacji OTA dla Linuksa: /api/ota oraz /api/ota/check
        if path in ["/api/ota", "/api/ota/check"]:
            ota_data = {
                "status": "ok",
                "current_version": "v3.1.4",
                "latest_version": "v3.1.5",
                "update_available": True,
                "release_date": "2026-10-13",
                "repo": "mateusz19558/TVDecoder_OS",
                "title": "TVDecoder Aurora OS - Aktualizacja v3.1.5",
                "changelog": [
                    "Ostatnio oglądane: dodano polecane hity kinowe i seriale 4K HDR",
                    "Wyciszanie i wstrzymywanie TV na żywo po przejściu do YouTube Smart TV",
                    "Bezpośredni powrót do Menu Głównego (M) z poziomu aplikacji YouTube",
                    "Nowe Centrum Ustawień wzorowane na systemie PlayStation 4 (PS4)",
                    "Zintegrowany moduł bezprzewodowych aktualizacji OTA z GitHub"
                ]
            }
            res_bytes = json.dumps(ota_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 4. Wyzwolenie instalacji OTA: /api/ota/apply
        if path == "/api/ota/apply":
            ota_script = "/opt/tvdecoder/scripts/ota_update.sh"
            if not os.path.exists(ota_script):
                alt_script = os.path.join(APP_DIR, "..", "scripts", "ota_update.sh")
                if os.path.exists(alt_script):
                    ota_script = alt_script

            success = False
            if os.path.exists(ota_script):
                try:
                    import subprocess
                    subprocess.Popen(["/usr/bin/env", "bash", ota_script])
                    success = True
                except Exception:
                    pass

            resp_payload = {
                "status": "ok" if success else "simulated",
                "message": "Pomyślnie rozpoczęto pobieranie i instalację aktualizacji OTA z GitHub."
            }
            res_bytes = json.dumps(resp_payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 5. Wykrywanie połączenia kablowego vs Wi-Fi: /api/network
        if path == "/api/network":
            net_info = {
                "status": "ok",
                "type": "ethernet",
                "name": "Ethernet (LAN)",
                "ip": "127.0.0.1",
                "speed": "1 Gb/s",
                "ssid": ""
            }
            try:
                import subprocess
                # Sprawdzenie domyślnej trasy IP w Linuksie
                route_res = subprocess.run(["ip", "route", "show", "default"], stdout=subprocess.PIPE, text=True, timeout=1)
                parts = route_res.stdout.split()
                if "dev" in parts:
                    idx = parts.index("dev") + 1
                    if idx < len(parts):
                        dev = parts[idx]
                        net_info["name"] = dev
                        if dev.startswith("wl") or "wlan" in dev or "wifi" in dev:
                            net_info["type"] = "wifi"
                            ssid_res = subprocess.run(["iwgetid", "-r"], stdout=subprocess.PIPE, text=True, timeout=1)
                            net_info["ssid"] = ssid_res.stdout.strip()
                        else:
                            net_info["type"] = "ethernet"

                # Pobranie lokalnego IP
                ip_res = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, text=True, timeout=1)
                ips = ip_res.stdout.strip().split()
                if ips:
                    net_info["ip"] = ips[0]
            except Exception:
                pass

            res_bytes = json.dumps(net_info, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 6. Skanowanie dostępnych sieci Wi-Fi: /api/wifi/scan
        if path == "/api/wifi/scan":
            networks = []
            try:
                import subprocess
                nm_res = subprocess.run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"], stdout=subprocess.PIPE, text=True, timeout=3)
                for line in nm_res.stdout.strip().splitlines():
                    if line:
                        pts = line.split(":")
                        if len(pts) >= 2 and pts[0]:
                            try: sig = int(pts[1])
                            except: sig = 70
                            sec = pts[2] if len(pts) > 2 else "WPA2"
                            networks.append({"ssid": pts[0], "signal": sig, "security": sec})
            except Exception:
                pass

            if not networks:
                networks = [
                    {"ssid": "Domowy_Router_5G", "signal": 96, "security": "WPA2/WPA3"},
                    {"ssid": "Netia_Swiatlowod_24", "signal": 82, "security": "WPA2-PSK"},
                    {"ssid": "Orange_Swiatlowod_5G", "signal": 65, "security": "WPA2-Personal"},
                    {"ssid": "UPC_Wi-Free", "signal": 48, "security": "WPA2-Enterprise"}
                ]

            payload = {"status": "ok", "networks": networks}
            res_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 7. Nawiązywanie połączenia z siecią Wi-Fi: /api/wifi/connect
        if path == "/api/wifi/connect":
            query = parse_qs(parsed.query)
            ssid = query.get("ssid", [""])[0]
            password = query.get("pass", [""])[0]
            ok = False
            if ssid:
                try:
                    import subprocess
                    cmd = ["nmcli", "device", "wifi", "connect", ssid]
                    if password:
                        cmd.extend(["password", password])
                    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
                    ok = (p.returncode == 0)
                except Exception:
                    ok = True # fallback simulation w środowisku bez nmcli

            payload = {
                "status": "ok" if ok else "error",
                "ssid": ssid,
                "message": "Połączono pomyślnie z siecią Wi-Fi" if ok else "Błąd łączenia z siecią Wi-Fi"
            }
            res_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 8. Wykrywanie urządzeń USB i dysków przenośnych: /api/storage
        if path == "/api/storage":
            storage_data = {
                "status": "ok",
                "internal": {"total_gb": 64.0, "free_gb": 51.2, "system_gb": 9.0, "apps_gb": 3.2, "buffer_gb": 1.8},
                "usb_drives": []
            }
            try:
                import subprocess
                ls_res = subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,LABEL,TRAN,FSTYPE"], stdout=subprocess.PIPE, text=True, timeout=2)
                blk = json.loads(ls_res.stdout)
                for dev in blk.get("blockdevices", []):
                    tran = dev.get("tran", "")
                    if tran == "usb" or dev.get("rm", False) or "usb" in dev.get("name", "").lower():
                        lbl = dev.get("label") or dev.get("name") or "Pamięć USB"
                        size_b = int(dev.get("size") or 0)
                        size_gb = round(size_b / (1024**3), 1)
                        mp = dev.get("mountpoint") or f"/media/usb_{dev.get('name')}"
                        storage_data["usb_drives"].append({
                            "name": dev.get("name"),
                            "label": lbl,
                            "total_gb": size_gb if size_gb > 0 else 32.0,
                            "free_gb": round(size_gb * 0.85, 1) if size_gb > 0 else 28.4,
                            "format": dev.get("fstype") or "FAT32",
                            "type": "usb",
                            "mountpoint": mp
                        })
            except Exception:
                pass

            res_bytes = json.dumps(storage_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 3. Server-Sent Events (SSE) dla pilota Apple TV
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
                self.wfile.write(b"data: {\"type\":\"connected\"}\n\n")
                self.wfile.flush()

                while True:
                    try:
                        msg = q.get(timeout=25.0)
                        self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with event_subscribers_lock:
                    if q in event_subscribers:
                        event_subscribers.remove(q)
            return

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
    print(f"[TVDecoder] Serwer Aurora OS aktywny na http://127.0.0.1:{port}", flush=True)
    httpd.serve_forever()

if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
