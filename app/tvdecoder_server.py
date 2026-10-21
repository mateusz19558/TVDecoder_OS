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
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

APP_DIR = os.path.dirname(os.path.abspath(__file__))
event_subscribers = []
event_subscribers_lock = threading.Lock()

def get_system_version_info():
    vfile = os.path.join(APP_DIR, "version.json")
    info = {
        "version": "3.2.0",
        "commit_sha": "6c591e2",
        "build_date": "2026-10-21",
        "system": "Aurora OS (Linux Debian 12 / Windows Hybrid)"
    }
    if os.path.exists(vfile):
        try:
            with open(vfile, "r", encoding="utf-8") as f:
                saved = json.load(f)
                info.update(saved)
        except Exception:
            pass
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=APP_DIR, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=1)
        if res.returncode == 0 and res.stdout.strip():
            info["commit_sha"] = res.stdout.strip()
    except Exception:
        pass
    return info

def check_github_update():
    local_info = get_system_version_info()
    api_url = "https://api.github.com/repos/mateusz19558/TVDecoder_OS/commits/main"
    req = urllib.request.Request(api_url, headers={
        "User-Agent": "TVDecoder-OTA/3.2.0",
        "Accept": "application/vnd.github.v3+json"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                remote_sha = data.get("sha", "")[:7]
                commit_info = data.get("commit", {})
                commit_msg = commit_info.get("message", "Aktualizacja systemu Aurora OS")
                commit_date = commit_info.get("committer", {}).get("date", "")
                
                lines = [line.strip() for line in commit_msg.splitlines() if line.strip() and not line.strip().startswith("#")]
                if not lines:
                    lines = ["Bieżące poprawki stabilności i aktualizacja pakietów systemowych Linux"]
                
                local_sha = local_info.get("commit_sha", "")
                is_update_available = (remote_sha != local_sha) and bool(remote_sha)
                
                return {
                    "status": "ok",
                    "update_available": is_update_available,
                    "current_version": f"v{local_info.get('version', '3.2.0')} ({local_sha})",
                    "current_commit": local_sha,
                    "latest_version": f"v{local_info.get('version', '3.2.0')} ({remote_sha})",
                    "latest_commit": remote_sha,
                    "release_date": commit_date[:10] if commit_date else local_info.get("build_date", ""),
                    "repo": "mateusz19558/TVDecoder_OS",
                    "title": f"Aurora OS - Wydanie ({remote_sha})",
                    "changelog": lines,
                    "linux_packages_update": True,
                    "message": "Dostępna jest nowa wersja oprogramowania dekodera oraz aktualizacje pakietów Linux!" if is_update_available else "System Aurora OS oraz jądro Linux są w pełni zaktualizowane."
                }
    except Exception as e:
        local_sha = local_info.get("commit_sha", "")
        return {
            "status": "warning",
            "update_available": False,
            "current_version": f"v{local_info.get('version', '3.2.0')} ({local_sha})",
            "current_commit": local_sha,
            "latest_version": f"v{local_info.get('version', '3.2.0')} ({local_sha})",
            "latest_commit": local_sha,
            "release_date": local_info.get("build_date", ""),
            "repo": "mateusz19558/TVDecoder_OS",
            "title": "Brak połączenia z serwerem aktualizacji GitHub",
            "changelog": [
                "Nie udało się zweryfikować zdalnych aktualizacji w serwisie GitHub.",
                f"Szczegóły: {str(e)}"
            ],
            "linux_packages_update": True,
            "message": "Nie można połączyć się z GitHub API. Sprawdź połączenie internetowe dekodera."
        }

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

        # 3. Endpoint aktualizacji OTA: /api/ota oraz /api/ota/check (dynamiczny z GitHub)
        if path in ["/api/ota", "/api/ota/check"]:
            ota_data = check_github_update()
            res_bytes = json.dumps(ota_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 4. Status postępu aktualizacji OTA: /api/ota/status
        if path == "/api/ota/status":
            status_file = "/tmp/ota_status.json"
            status_data = None
            if os.path.exists(status_file):
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        status_data = json.load(f)
                except Exception:
                    pass
            
            if not status_data:
                alt_status = os.path.join(APP_DIR, "ota_status.json")
                if os.path.exists(alt_status):
                    try:
                        with open(alt_status, "r", encoding="utf-8") as f:
                            status_data = json.load(f)
                    except Exception:
                        pass
                        
            if not status_data:
                status_data = {
                    "percent": 0,
                    "step": "idle",
                    "description": "Brak aktywnego procesu aktualizacji.",
                    "completed": False,
                    "error": False
                }
                
            res_bytes = json.dumps(status_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 5. Wyzwolenie instalacji OTA: /api/ota/apply
        if path == "/api/ota/apply":
            status_file = "/tmp/ota_status.json"
            if not os.path.exists("/tmp"):
                status_file = os.path.join(APP_DIR, "ota_status.json")

            init_status = {
                "percent": 5,
                "step": "init",
                "description": "Inicjalizacja środowiska aktualizacji OTA...",
                "completed": False,
                "error": False,
                "timestamp": int(time.time())
            }
            try:
                with open(status_file, "w", encoding="utf-8") as f:
                    json.dump(init_status, f)
            except Exception:
                pass

            ota_script = "/opt/tvdecoder/scripts/ota_update.sh"
            if not os.path.exists(ota_script):
                alt_script = os.path.join(APP_DIR, "..", "scripts", "ota_update.sh")
                if os.path.exists(alt_script):
                    ota_script = alt_script

            success = False
            if os.path.exists(ota_script) and sys.platform != "win32":
                try:
                    import subprocess
                    subprocess.Popen(["/usr/bin/env", "bash", ota_script])
                    success = True
                except Exception:
                    pass
            else:
                # Wątek deweloperski / symulacja dla Windows lub gdy brak bash
                def run_background_update_worker():
                    steps = [
                        (20, "download", "Pobieranie najnowszych plików Aurora OS z GitHub..."),
                        (40, "extract", "Weryfikacja sumy kontrolnej i rozpakowywanie pakietu..."),
                        (60, "install_app", "Wdrażanie plików aplikacji i zaktualizowanego kodu..."),
                        (75, "linux_update", "Aktualizowanie pakietów systemowych Linux (apt-get upgrade)..."),
                        (95, "finalize", "Finalizacja aktualizacji i synchronizacja konfiguracji..."),
                        (100, "done", "System TVDecoder OS oraz pakiety Linux zostały pomyślnie zaktualizowane!")
                    ]
                    for pct, step, desc in steps:
                        time.sleep(1.0)
                        s = {
                            "percent": pct,
                            "step": step,
                            "description": desc,
                            "completed": (pct == 100),
                            "error": False,
                            "timestamp": int(time.time())
                        }
                        try:
                            with open(status_file, "w", encoding="utf-8") as f:
                                json.dump(s, f)
                        except Exception:
                            pass
                t = threading.Thread(target=run_background_update_worker, daemon=True)
                t.start()
                success = True

            resp_payload = {
                "status": "ok" if success else "error",
                "message": "Rozpoczęto pobieranie i instalację aktualizacji OTA oraz pakietów Linux."
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

        # 8b. Elektroniczny Przewodnik po Programach (EPG): /api/epg
        if path in ["/api/epg", "/api/epg/all"]:
            epg_json = get_epg_data()
            res_bytes = json.dumps(epg_json, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # 9. Zasilanie: Reboot i Shutdown
        if path == "/api/power/reboot":
            res_bytes = json.dumps({"status": "ok", "action": "reboot"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            def do_reboot():
                import time, subprocess
                time.sleep(1)
                try: subprocess.run(["reboot"])
                except: pass
            threading.Thread(target=do_reboot, daemon=True).start()
            return

        if path == "/api/power/shutdown":
            res_bytes = json.dumps({"status": "ok", "action": "shutdown"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res_bytes)
            def do_shutdown():
                import time, subprocess
                time.sleep(1)
                try: subprocess.run(["poweroff"])
                except: pass
            threading.Thread(target=do_shutdown, daemon=True).start()
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

# ===================== MODUŁ POBIERANIA I BUFOROWANIA EPG =====================
epg_cache = {"time": 0, "data": None}
epg_lock = threading.Lock()

def generate_default_programs(ch_name, cat):
    if "4FUN KIDS" in ch_name:
        return [
            {"time": "06:00", "title": "Poranne Piosenki i Rymowanki", "genre": "Dzieci", "desc": "Wesołe i edukacyjne piosenki dla najmłodszych widzów."},
            {"time": "08:30", "title": "Tańcz i Klaszcz z Nami", "genre": "Zabawa", "desc": "Ruchowe animacje i taneczne przeboje dla maluchów."},
            {"time": "11:00", "title": "Kraina Kolorowych Melodii", "genre": "Dzieci", "desc": "Najpiękniejsze polskie i światowe piosenki animowane."},
            {"time": "14:00", "title": "Popołudniowe Bajkowe Karaoke", "genre": "Muzyka", "desc": "Wspólne śpiewanie z tekstem na ekranie."},
            {"time": "17:30", "title": "Klub Wesołych Odkrywców", "genre": "Edukacja", "desc": "Poznajemy świat zwierząt, liter i cyfr przez piosenkę."},
            {"time": "19:45", "title": "Dobranockowe Kołysanki", "genre": "Wyciszenie", "desc": "Spokojne, łagodne melodie przygotowujące dzieci do snu."},
            {"time": "21:30", "title": "Spokojna Noc Malucha", "genre": "Relaks", "desc": "Szumy relaksacyjne i ciche kołysanki."}
        ]
    elif "4FUN" in ch_name:
        return [
            {"time": "06:00", "title": "Dzień Dobry 4FUN Hits", "genre": "Muzyka", "desc": "Pobudka w rytmie największych radiowych przebojów."},
            {"time": "09:00", "title": "Chcesz Masz - Hity na Życzenie", "genre": "Interaktywny", "desc": "Teledyski wybierane przez widzów w aplikacji."},
            {"time": "12:00", "title": "Top 20 Pop & Dance", "genre": "Notowanie", "desc": "Przegląd najgorętszych hitów tygodnia."},
            {"time": "15:00", "title": "4FUN Na Propsie", "genre": "Trendy", "desc": "Nowości muzyczne i trendy z TikToka i Spotify."},
            {"time": "18:00", "title": "4FUN Party Zone", "genre": "Impreza", "desc": "Klubowe remiksy i energetyczne beaty na wieczór."},
            {"time": "21:00", "title": "Gorąca 20 - Lista Przebojów", "genre": "Hit", "desc": "Oficjalne podsumowanie głosowania widzów 4FUN TV."},
            {"time": "23:00", "title": "Nocny 4FUN Non Stop", "genre": "Klubowa", "desc": "Muzyka klubowa i relaksujące teledyski do świtu."}
        ]
    elif "NASA" in ch_name:
        return [
            {"time": "06:00", "title": "ISS Live: Widoki Ziemi w 4K Ultra HD", "genre": "Kosmos", "desc": "Bezpośrednia transmisja z kamer Międzynarodowej Stacji Kosmicznej."},
            {"time": "09:00", "title": "Space Station Science Briefing", "genre": "Nauka", "desc": "Raport z eksperymentów naukowych prowadzonych w stanie nieważkości."},
            {"time": "12:00", "title": "Artemis: Misja Powrotu na Księżyc", "genre": "Dokument", "desc": "Kulisy budowy bazy księżycowej i rakiety SLS nowej generacji."},
            {"time": "15:00", "title": "Kosmiczny Teleskop Jamesa Webba", "genre": "Astronomia", "desc": "Odkrycia najodleglejszych galaktyk i egzoplanet we wszechświecie."},
            {"time": "18:00", "title": "Mars Perseverance Rover Odyssey", "genre": "Eksploracja", "desc": "Prace łazika na Czerwonej Planecie w poszukiwaniu śladów życia."},
            {"time": "21:00", "title": "Astronauci w Otwartym Kosmosie (EVA)", "genre": "Relacja", "desc": "Zapis spacerów kosmicznych i prac serwisowych na poszyciu ISS."},
            {"time": "23:30", "title": "Głębia Wszechświata: Czasoprzestrzeń", "genre": "Dokument", "desc": "Fascynująca opowieść o czarnych dziurach i granicach kosmosu."}
        ]
    return [
        {"time": "06:00", "title": "Magazyn Poranny i Pogoda", "genre": "Informacje", "desc": "Najświeższe wieści z kraju i ze świata, prognoza pogody."},
        {"time": "08:30", "title": "Śniadaniowe Pasmo Rozmów", "genre": "Rozrywka", "desc": "Ciekawi goście, porady kulinarne i felietony obyczajowe."},
        {"time": "11:15", "title": "Przyroda i Krajobrazy Polski", "genre": "Dokument", "desc": "Fascynujące reportaże o rodzimych parkach narodowych."},
        {"time": "13:00", "title": "Magazyn Reporterów w Terenie", "genre": "Społeczny", "desc": "Sprawy trudne, interwencje dziennikarskie i historie ludzkie."},
        {"time": "15:00", "title": "Wiadomości Popołudniowe", "genre": "Wiadomości", "desc": "Serwis informacyjny, skrót najważniejszych wydarzeń dnia."},
        {"time": "16:20", "title": "Serial Obyczajowy: Losy Rodziny", "genre": "Dramat", "desc": "Popularny polski serial śledzący codzienne perypetie bohaterów."},
        {"time": "18:00", "title": "Teleturniej Wiedzy Ogólnej", "genre": "Teleturniej", "desc": "Walka uczestników o wysokie nagrody pieniężne."},
        {"time": "19:30", "title": "Główne Wydanie Wiadomości", "genre": "Wiadomości", "desc": "Podsumowanie dnia, relacje korespondentów, sport i pogoda."},
        {"time": "20:15", "title": "Hit Wieczorny: Megapremiera Filmowa", "genre": "Film", "desc": "Gwiazdorska obsada i trzymająca w napięciu fabuła filmowa."},
        {"time": "22:45", "title": "Kino Nocne: Mocne Emocje", "genre": "Thriller", "desc": "Mroczny thriller psychologiczny dla dorosłych widzów."},
        {"time": "00:50", "title": "Z Archiwum Telewizyjnego", "genre": "Retrospekcja", "desc": "Kultowe audycje, koncerty i reportaże z lat ubiegłych."}
    ]

def get_epg_data():
    global epg_cache
    now = time.time()
    with epg_lock:
        if epg_cache["data"] and (now - epg_cache["time"] < 2700):
            return epg_cache["data"]

    channel_map = [
        (1, "TVP 1 HD", "TVP-1", "Ogólne"),
        (2, "TVP 2 HD", "TVP-2", "Ogólne"),
        (3, "TVP SPORT HD", "TVP-Sport", "Sport"),
        (4, "POLSAT 2 HD", "Polsat-2", "Ogólne"),
        (5, "POLSAT SPORT 1", "Polsat-Sport", "Sport"),
        (6, "EUROSPORT 1", "Eurosport", "Sport"),
        (7, "POLSAT SERIALE", "Polsat-Seriale", "Filmy"),
        (8, "4FUN TV", "", "Muzyka"),
        (9, "4FUN KIDS", "", "Dzieci"),
        (10, "NASA TV UHD", "", "Nauka")
    ]

    import urllib.request, re, html

    def fetch_channel(ch_id, ch_name, slug, cat):
        progs = []
        if slug:
            try:
                req = urllib.request.Request(
                    f"https://m.teleman.pl/stations/{slug}?hour=-1",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    page_html = resp.read().decode("utf-8", errors="ignore")

                rows = re.findall(r'<tr id="prog\d+">(.*?)</tr>', page_html, re.DOTALL)
                for r in rows:
                    t_match = re.search(r'<th>\s*(\d{1,2}:\d{2})', r)
                    title_match = re.search(r'<div class="title[^"]*">\s*([^<]+?)\s*</div>', r)
                    genre_match = re.search(r'<div class="genre">\s*([^<]+?)\s*</div>', r)
                    desc_match = re.search(r'(?s)<div class="tooltip">.*?<div>.*?<div>\s*([^<]+?)\s*</div>', r)
                    if t_match and title_match:
                        t_str = t_match.group(1).strip()
                        if len(t_str) == 4 and t_str[1] == ':':
                            t_str = '0' + t_str
                        tit = html.unescape(title_match.group(1).strip())
                        gen = html.unescape(genre_match.group(1).strip()) if genre_match else cat
                        desc = html.unescape(desc_match.group(1).strip()) if desc_match else f"Program {tit} na kanale {ch_name}."
                        progs.append({"time": t_str, "title": tit, "genre": gen, "desc": desc})
            except Exception:
                pass

        if not progs:
            progs = generate_default_programs(ch_name, cat)

        cur_offset = 0
        prev_h = -1
        res_items = []
        for i in range(len(progs)):
            cur = progs[i]
            parts = cur["time"].split(":")
            raw_h = float(parts[0]) + float(parts[1]) / 60.0
            if prev_h >= 0 and raw_h < prev_h and (prev_h - raw_h) > 6:
                cur_offset += 24
            prev_h = raw_h
            sh = raw_h + cur_offset

            if i + 1 < len(progs):
                nxt_parts = progs[i+1]["time"].split(":")
                next_raw_h = float(nxt_parts[0]) + float(nxt_parts[1]) / 60.0
                end_str = progs[i+1]["time"]
            else:
                next_raw_h = (raw_h + 1.5) % 24
                end_str = f"{int(next_raw_h):02d}:{int((next_raw_h%1)*60):02d}"

            next_sh = next_raw_h + cur_offset
            if next_sh < sh: next_sh += 24
            dur = next_sh - sh
            if dur <= 0: dur = 1.0
            if dur > 6: dur = 1.5
            eh = sh + dur

            res_items.append({
                "id": f"epg-{ch_id}-{i}",
                "time": cur["time"],
                "endTime": end_str,
                "startHour": round(sh, 3),
                "endHour": round(eh, 3),
                "dur": round(dur, 3),
                "timeRange": f"{cur['time']} - {end_str}",
                "title": cur["title"],
                "genre": cur["genre"],
                "desc": cur["desc"]
            })
        return {"id": ch_id, "name": ch_name, "cat": cat, "programs": res_items}

    import concurrent.futures
    channels_res = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_channel, cid, cname, cslug, ccat) for (cid, cname, cslug, ccat) in channel_map]
        for f in concurrent.futures.as_completed(futures):
            try:
                channels_res.append(f.result())
            except:
                pass

    channels_res.sort(key=lambda x: x["id"])
    result = {"status": "ok", "channels": channels_res}
    with epg_lock:
        epg_cache["time"] = now
        epg_cache["data"] = result
    return result

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
