#!/usr/bin/env python3
# ==============================================================================
# TVDecoder OS - 100% Natywny Program Dekodera Telewizyjnego (Zero HTML)
# Architektura: PyQt5 + QPainter OSD Engine + mpv Video Engine
# ==============================================================================

import os
import sys
import json
import time
import signal
import datetime
import subprocess
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Sprawdzenie dostępności PyQt5
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                                 QVBoxLayout, QHBoxLayout, QStackedWidget)
    from PyQt5.QtCore import Qt, QTimer, QRect, QPoint, pyqtSignal, QObject
    from PyQt5.QtGui import (QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, 
                            QPixmap, QKeySequence, QFontMetrics)
except ImportError:
    print("[TVDecoder] Błąd: Brak biblioteki PyQt5! Zainstaluj 'python3-pyqt5'.", file=sys.stderr)
    sys.exit(1)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CHANNELS_FILE = os.path.join(APP_DIR, "channels.json")
QR_FILE = os.path.join(APP_DIR, "apple_remote_qr.png")

# Sygnał do bezpiecznej komunikacji wątków API -> GUI
class RemoteSignalBridge(QObject):
    remote_key_signal = pyqtSignal(str)

bridge = RemoteSignalBridge()

# ==============================================================================
# 1. WBUDOWANY SERWER API DLA PILOTA APPLE TV (HOMEKIT)
# ==============================================================================
class RemoteApiHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/remote":
            query = parse_qs(parsed.query)
            key = query.get("key", [None])[0]
            if key:
                bridge.remote_key_signal.emit(key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        self.send_response(404)
        self.end_headers()

def start_api_server(port=8080):
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), RemoteApiHandler)
        server.serve_forever()
    except Exception as e:
        print(f"[TVDecoder] Serwer API port {port}: {e}")

# ==============================================================================
# 2. SILNIK ODTWARZANIA WIDEO (Natywny proces MPV z akceleracją sprzętową)
# ==============================================================================
class VideoPlayer:
    def __init__(self, win_id):
        self.win_id = win_id
        self.process = None
        self.current_url = None

    def play(self, url):
        self.stop()
        self.current_url = url
        cmd = [
            "mpv",
            f"--wid={self.win_id}",
            "--no-terminal",
            "--really-quiet",
            "--hwdec=auto",
            "--vo=gpu",
            "--audio-device=auto",
            "--cache=yes",
            "--demuxer-max-bytes=32MiB",
            "--demuxer-readahead-secs=10",
            url
        ]
        try:
            self.process = subprocess.Popen(cmd)
        except Exception as e:
            print(f"[TVDecoder Player] Błąd uruchomienia mpv: {e}")

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=0.8)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

# ==============================================================================
# 3. GŁÓWNE OKNO NATIVE AURORA TV DECODER (100% KOD PROGRAMU)
# ==============================================================================
class TVDecoderNativeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TVDecoder OS - Aurora Native STB")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: black;")
        self.setCursor(Qt.BlankCursor) # Ukryj kursor myszy na telewizorze

        # Dane kanałów
        self.channels = self.load_channels()
        self.current_ch_idx = 0

        # Stan OSD (warstwy)
        self.osd_mode = "banner" # banner, epg, menu, settings, none
        self.osd_timer_ms = 6000
        self.volume = 80
        self.show_volume_timer = 0
        self.dial_buffer = ""
        self.dial_timer = 0

        # Nawigacja EPG
        self.epg_selected_idx = 0
        self.menu_selected_idx = 0
        self.settings_selected_idx = 0

        # Podłączenie sygnału pilota
        bridge.remote_key_signal.connect(self.handle_remote_cmd)

        # Timer odświeżania OSD i zegarka
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.on_timer_tick)
        self.ui_timer.start(50) # 20 FPS odświeżania OSD

        # Widżet wideo i widżet OSD
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.player = None

        # Automatyczne uruchomienie pełnego ekranu
        self.showFullScreen()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.player:
            win_id = int(self.central_widget.winId())
            self.player = VideoPlayer(win_id)
            self.play_current_channel()

    def load_channels(self):
        if os.path.exists(CHANNELS_FILE):
            try:
                with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Domyślna lista awaryjna
        return [
            {"number": 1, "name": "TVP 1 HD", "category": "Ogólne", "url": "http://57.128.210.196:8080/144/index.m3u8"},
            {"number": 2, "name": "TVP 2 HD", "category": "Ogólne", "url": "http://57.128.210.196:8080/143/index.m3u8"},
            {"number": 3, "name": "TVP SPORT HD", "category": "Sport", "url": "http://57.128.210.196:8080/134/index.m3u8"}
        ]

    def play_current_channel(self):
        if not self.channels:
            return
        ch = self.channels[self.current_ch_idx]
        print(f"[TVDecoder] Przełączanie na: [{ch.get('number')}] {ch.get('name')}", flush=True)
        if self.player:
            self.player.play(ch.get("url"))
        self.osd_mode = "banner"
        self.osd_timer_ms = 6000
        self.update()

    def on_timer_tick(self):
        need_update = False
        if self.osd_timer_ms > 0:
            self.osd_timer_ms -= 50
            if self.osd_timer_ms <= 0 and self.osd_mode == "banner":
                self.osd_mode = "none"
                need_update = True

        if self.show_volume_timer > 0:
            self.show_volume_timer -= 50
            need_update = True

        if self.dial_timer > 0:
            self.dial_timer -= 50
            if self.dial_timer <= 0 and self.dial_buffer:
                self.commit_dial_channel()
            need_update = True

        if need_update or self.osd_mode != "none":
            self.update()

    def commit_dial_channel(self):
        try:
            target_num = int(self.dial_buffer)
            for idx, ch in enumerate(self.channels):
                if ch.get("number") == target_num:
                    self.current_ch_idx = idx
                    self.play_current_channel()
                    break
        except Exception:
            pass
        self.dial_buffer = ""

    # ==========================================================================
    # 4. OBSŁUGA KLAWISZY PILOTA I KLAWIATURY
    # ==========================================================================
    def keyPressEvent(self, event):
        k = event.key()
        if k in (Qt.Key_Up, Qt.Key_W):
            self.handle_remote_cmd("up")
        elif k in (Qt.Key_Down, Qt.Key_S):
            self.handle_remote_cmd("down")
        elif k in (Qt.Key_Left, Qt.Key_A):
            self.handle_remote_cmd("left")
        elif k in (Qt.Key_Right, Qt.Key_D):
            self.handle_remote_cmd("right")
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self.handle_remote_cmd("select")
        elif k in (Qt.Key_Escape, Qt.Key_Backspace):
            self.handle_remote_cmd("back")
        elif k in (Qt.Key_M, Qt.Key_Menu):
            self.handle_remote_cmd("exit")
        elif k == Qt.Key_I:
            self.handle_remote_cmd("info")
        elif k in (Qt.Key_Plus, Qt.Key_BracketRight):
            self.handle_remote_cmd("vol_up")
        elif k in (Qt.Key_Minus, Qt.Key_BracketLeft):
            self.handle_remote_cmd("vol_down")
        elif k in (Qt.Key_F2,):
            self.launch_youtube()
        elif Qt.Key_0 <= k <= Qt.Key_9:
            self.digit_pressed(str(k - Qt.Key_0))
        else:
            super().keyPressEvent(event)

    def digit_pressed(self, d):
        if len(self.dial_buffer) < 3:
            self.dial_buffer += d
            self.dial_timer = 1500
            self.update()

    def handle_remote_cmd(self, cmd):
        if self.osd_mode == "none":
            if cmd == "up":
                self.current_ch_idx = (self.current_ch_idx + 1) % len(self.channels)
                self.play_current_channel()
            elif cmd == "down":
                self.current_ch_idx = (self.current_ch_idx - 1 + len(self.channels)) % len(self.channels)
                self.play_current_channel()
            elif cmd in ("select", "info"):
                self.osd_mode = "banner"
                self.osd_timer_ms = 6000
            elif cmd == "exit":
                self.osd_mode = "menu"
            elif cmd == "back":
                self.osd_mode = "epg"
            elif cmd == "vol_up":
                self.volume = min(100, self.volume + 5)
                self.show_volume_timer = 2000
            elif cmd == "vol_down":
                self.volume = max(0, self.volume - 5)
                self.show_volume_timer = 2000
            self.update()
            return

        if self.osd_mode == "banner":
            if cmd in ("up", "down"):
                delta = 1 if cmd == "up" else -1
                self.current_ch_idx = (self.current_ch_idx + delta) % len(self.channels)
                self.play_current_channel()
            elif cmd in ("back", "exit"):
                self.osd_mode = "none"
            elif cmd == "select":
                self.osd_mode = "epg"
            self.update()
            return

        if self.osd_mode == "epg":
            if cmd == "up":
                self.epg_selected_idx = max(0, self.epg_selected_idx - 1)
            elif cmd == "down":
                self.epg_selected_idx = min(len(self.channels) - 1, self.epg_selected_idx + 1)
            elif cmd == "select":
                self.current_ch_idx = self.epg_selected_idx
                self.play_current_channel()
            elif cmd in ("back", "exit"):
                self.osd_mode = "none"
            self.update()
            return

        if self.osd_mode == "menu":
            menu_items_count = 5
            if cmd == "left":
                self.menu_selected_idx = (self.menu_selected_idx - 1 + menu_items_count) % menu_items_count
            elif cmd == "right":
                self.menu_selected_idx = (self.menu_selected_idx + 1) % menu_items_count
            elif cmd == "select":
                if self.menu_selected_idx == 0:
                    self.osd_mode = "none"
                elif self.menu_selected_idx == 1:
                    self.osd_mode = "epg"
                elif self.menu_selected_idx == 2:
                    self.launch_youtube()
                elif self.menu_selected_idx == 3:
                    self.osd_mode = "settings"
                elif self.menu_selected_idx == 4:
                    self.close()
            elif cmd in ("back", "exit"):
                self.osd_mode = "none"
            self.update()
            return

        if self.osd_mode == "settings":
            if cmd in ("back", "exit"):
                self.osd_mode = "menu"
            self.update()
            return

    def launch_youtube(self):
        yt_script = "/opt/tvdecoder/config/launch_youtube_tv.sh"
        if os.path.exists(yt_script):
            subprocess.Popen([yt_script])

    # ==========================================================================
    # 5. NATYWNY SILNIK RYSOWANIA GUI W KODZIE CZYSTYM (QPainter - ZERO HTML)
    # ==========================================================================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()

        # Zegar w prawym górnym rogu ekranu
        self.draw_header_clock(painter, w, h)

        # Warstwy interfejsu
        if self.osd_mode == "banner":
            self.draw_info_banner(painter, w, h)
        elif self.osd_mode == "epg":
            self.draw_epg_grid(painter, w, h)
        elif self.osd_mode == "menu":
            self.draw_dashboard_menu(painter, w, h)
        elif self.osd_mode == "settings":
            self.draw_settings_screen(painter, w, h)

        # Pasek głośności
        if self.show_volume_timer > 0:
            self.draw_volume_bar(painter, w, h)

        # Wybieranie numeru kanału
        if self.dial_buffer and self.dial_timer > 0:
            self.draw_dialing_badge(painter, w, h)

    def draw_header_clock(self, p, w, h):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        rect = QRect(w - 170, 25, 140, 40)
        p.setBrush(QBrush(QColor(15, 23, 42, 180)))
        p.setPen(QPen(QColor(56, 189, 248, 120), 1))
        p.drawRoundedRect(rect, 8, 8)

        p.setPen(QColor(241, 245, 249))
        p.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        p.drawText(rect, Qt.AlignCenter, now_str)

    def draw_info_banner(self, p, w, h):
        ch = self.channels[self.current_ch_idx] if self.channels else {}
        margin = 50
        banner_h = 180
        banner_y = h - banner_h - margin
        banner_w = w - (margin * 2)
        rect = QRect(margin, banner_y, banner_w, banner_h)

        # Tło panelu (Glassmorphism Dark)
        gradient = QLinearGradient(0, banner_y, 0, banner_y + banner_h)
        gradient.setColorAt(0.0, QColor(15, 23, 42, 235))
        gradient.setColorAt(1.0, QColor(10, 15, 29, 245))
        p.setBrush(QBrush(gradient))
        p.setPen(QPen(QColor(14, 165, 233, 180), 2))
        p.drawRoundedRect(rect, 16, 16)

        # Plakietka numeru kanału
        num_rect = QRect(margin + 25, banner_y + 25, 80, 52)
        p.setBrush(QBrush(QColor(2, 132, 199)))
        p.setPen(QPen(QColor(56, 189, 248), 2))
        p.drawRoundedRect(num_rect, 10, 10)

        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("DejaVu Sans", 24, QFont.Bold))
        num_str = f"{ch.get('number', self.current_ch_idx+1):02d}"
        p.drawText(num_rect, Qt.AlignCenter, num_str)

        # Nazwa kanału
        p.setFont(QFont("DejaVu Sans", 22, QFont.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(margin + 125, banner_y + 50, ch.get("name", "Kanał TV"))

        # Kategoria i stan
        p.setFont(QFont("DejaVu Sans", 12))
        p.setPen(QColor(148, 163, 184))
        p.drawText(margin + 127, banner_y + 72, f"Kategoria: {ch.get('category', 'Telewizja')} • Na Żywo (HLS)")

        # Pasek postępu audycji
        bar_w = 300
        bar_x = margin + banner_w - bar_w - 35
        bar_y = banner_y + 40
        p.setBrush(QBrush(QColor(30, 41, 59)))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRect(bar_x, bar_y, bar_w, 8), 4, 4)

        p.setBrush(QBrush(QColor(14, 165, 233)))
        p.drawRoundedRect(QRect(bar_x, bar_y, int(bar_w * 0.65), 8), 4, 4)

        p.setFont(QFont("DejaVu Sans", 11, QFont.Bold))
        p.setPen(QColor(56, 189, 248))
        p.drawText(QRect(bar_x, bar_y - 22, bar_w, 20), Qt.AlignRight, "18:00 (65%) 19:30")

        # Tytuł bieżącego programu
        p.setFont(QFont("DejaVu Sans", 16, QFont.Bold))
        p.setPen(QColor(56, 189, 248))
        p.drawText(margin + 25, banner_y + 115, "18:00 - 19:30   Główny Serwis Informacyjny & Transmisja Live")

        # Opis
        p.setFont(QFont("DejaVu Sans", 13))
        p.setPen(QColor(203, 213, 225))
        p.drawText(margin + 25, banner_y + 142, "Bieżące relacje ze świata, pogoda, studio sportowe oraz najważniejsze wydarzenia dnia.")

        # Znaczniki jakości HD / 4K / Dolby
        badges = ["1080p FULL HD", "DOLBY AUDIO", "POL", "NA ŻYWO"]
        bx = margin + banner_w - 420
        by = banner_y + 115
        p.setFont(QFont("DejaVu Sans", 10, QFont.Bold))
        for b in badges:
            b_rect = QRect(bx, by, 95, 26)
            p.setBrush(QBrush(QColor(15, 23, 42, 200)))
            p.setPen(QPen(QColor(14, 165, 233, 140), 1))
            p.drawRoundedRect(b_rect, 6, 6)
            p.setPen(QColor(224, 242, 254))
            p.drawText(b_rect, Qt.AlignCenter, b)
            bx += 102

    def draw_epg_grid(self, p, w, h):
        # Przyciemnienie tła
        p.setBrush(QBrush(QColor(8, 12, 22, 230)))
        p.setPen(Qt.NoPen)
        p.drawRect(0, 0, w, h)

        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("DejaVu Sans", 24, QFont.Bold))
        p.drawText(60, 60, "PRZEWODNIK PO PROGRAMACH (EPG)")

        p.setFont(QFont("DejaVu Sans", 13))
        p.setPen(QColor(148, 163, 184))
        p.drawText(62, 90, "Wybierz stację za pomocą strzałek [▲] [▼]. Naciśnij [ENTER], aby przełączyć kanał, lub [ESC] aby wyjść.")

        # Lista kanałów EPG
        list_y = 130
        row_h = 65
        for i, ch in enumerate(self.channels):
            if i > 7: break # Limit widocznych na ekranie
            is_sel = (i == self.epg_selected_idx)
            is_cur = (i == self.current_ch_idx)

            row_rect = QRect(60, list_y, w - 120, row_h)
            if is_sel:
                p.setBrush(QBrush(QColor(14, 165, 233, 200)))
                p.setPen(QPen(QColor(255, 255, 255), 2))
            else:
                p.setBrush(QBrush(QColor(30, 41, 59, 140)))
                p.setPen(QPen(QColor(51, 65, 85, 120), 1))
            p.drawRoundedRect(row_rect, 10, 10)

            # Numer
            p.setFont(QFont("DejaVu Sans", 16, QFont.Bold))
            p.setPen(QColor(255, 255, 255) if is_sel else QColor(56, 189, 248))
            p.drawText(row_rect.x() + 25, row_rect.y() + 40, f"{ch.get('number', i+1):02d}")

            # Nazwa
            p.setFont(QFont("DejaVu Sans", 16, QFont.Bold))
            p.setPen(QColor(255, 255, 255))
            cur_tag = " • [OGLĄDASZ]" if is_cur else ""
            p.drawText(row_rect.x() + 85, row_rect.y() + 40, f"{ch.get('name')} {cur_tag}")

            # Program
            p.setFont(QFont("DejaVu Sans", 13))
            p.setPen(QColor(241, 245, 249) if is_sel else QColor(203, 213, 225))
            p.drawText(row_rect.x() + 450, row_rect.y() + 40, f"Pasmo Live: {ch.get('category')} • Transmisja bez przerw")

            list_y += row_h + 12

    def draw_dashboard_menu(self, p, w, h):
        p.setBrush(QBrush(QColor(8, 12, 22, 235)))
        p.setPen(Qt.NoPen)
        p.drawRect(0, 0, w, h)

        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("DejaVu Sans", 26, QFont.Bold))
        p.drawText(60, 70, "MENU GŁÓWNE AURORA BOX")

        p.setFont(QFont("DejaVu Sans", 14))
        p.setPen(QColor(148, 163, 184))
        p.drawText(62, 105, "Wybierz kafel za pomocą [◄] [►] i naciśnij [ENTER]. Naciśnij [ESC] aby wrócić do TV.")

        items = [
            ("📺 TELEWIZJA", "Oglądaj kanały na żywo"),
            ("📅 PROGRAM EPG", "Przewodnik po audycjach"),
            ("🔴 YOUTUBE SMART TV", "Oficjalny Leanback TV"),
            ("⚙️ USTAWIENIA & APPLE", "Pilot z iPhone i sieć"),
            ("🚪 WYJŚCIE", "Zamknij dekoder")
        ]

        card_w = (w - 120 - (len(items)-1)*20) // len(items)
        card_h = 240
        card_y = (h - card_h) // 2

        for i, (title, desc) in enumerate(items):
            card_x = 60 + i * (card_w + 20)
            rect = QRect(card_x, card_y, card_w, card_h)
            is_sel = (i == self.menu_selected_idx)

            if is_sel:
                p.setBrush(QBrush(QColor(14, 165, 233, 220)))
                p.setPen(QPen(QColor(255, 255, 255), 3))
            else:
                p.setBrush(QBrush(QColor(30, 41, 59, 160)))
                p.setPen(QPen(QColor(51, 65, 85, 140), 1))
            p.drawRoundedRect(rect, 16, 16)

            p.setFont(QFont("DejaVu Sans", 16, QFont.Bold))
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRect(card_x + 15, card_y + 40, card_w - 30, 80), Qt.AlignCenter | Qt.TextWordWrap, title)

            p.setFont(QFont("DejaVu Sans", 12))
            p.setPen(QColor(224, 242, 254) if is_sel else QColor(148, 163, 184))
            p.drawText(QRect(card_x + 15, card_y + 130, card_w - 30, 60), Qt.AlignCenter | Qt.TextWordWrap, desc)

    def draw_settings_screen(self, p, w, h):
        p.setBrush(QBrush(QColor(8, 12, 22, 245)))
        p.setPen(Qt.NoPen)
        p.drawRect(0, 0, w, h)

        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("DejaVu Sans", 24, QFont.Bold))
        p.drawText(60, 60, "USTAWIENIA DEKODERA • PILOT APPLE TV (IPHONE)")

        p.setFont(QFont("DejaVu Sans", 13))
        p.setPen(QColor(148, 163, 184))
        p.drawText(62, 90, "Steruj dekoderem za pomocą natywnego pilota w Centrum Sterowania iOS na swoim smartfonie.")

        # Lewa strona: Instrukcja
        left_w = w // 2 - 80
        p.setFont(QFont("DejaVu Sans", 15))
        p.setPen(QColor(241, 245, 249))
        p.drawText(60, 160, "1. Upewnij się, że iPhone i dekoder są w tej samej sieci Wi-Fi.")
        p.drawText(60, 205, "2. Otwórz aplikację Dom (Apple Home) na swoim iPhone.")
        p.drawText(60, 250, "3. Kliknij '+' -> 'Dodaj akcesorium' i zeskanuj kod z prawej strony.")
        p.drawText(60, 295, "4. Kod PIN parowania ręcznego:")

        # Box z kodem PIN
        pin_box = QRect(60, 320, 240, 55)
        p.setBrush(QBrush(QColor(88, 28, 135, 180)))
        p.setPen(QPen(QColor(168, 85, 247), 2))
        p.drawRoundedRect(pin_box, 10, 10)
        p.setFont(QFont("DejaVu Sans", 24, QFont.Bold))
        p.setPen(QColor(243, 232, 255))
        p.drawText(pin_box, Qt.AlignCenter, "111-22-333")

        p.setFont(QFont("DejaVu Sans", 12))
        p.setPen(QColor(148, 163, 184))
        p.drawText(60, 420, "Mostek Apple HomeKit HAP nasłuchuje na porcie 51827.")
        p.drawText(60, 445, "Status: Gotowy do wykrycia przez urządzenia iOS.")

        # Prawa strona: Kod QR
        qr_size = 280
        qr_x = w // 2 + 60
        qr_y = 150
        qr_rect = QRect(qr_x, qr_y, qr_size, qr_size)

        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.setPen(QPen(QColor(168, 85, 247), 4))
        p.drawRoundedRect(QRect(qr_x - 15, qr_y - 15, qr_size + 30, qr_size + 50), 16, 16)

        if os.path.exists(QR_FILE):
            pix = QPixmap(QR_FILE)
            p.drawPixmap(qr_rect, pix)
        else:
            p.setPen(QColor(0, 0, 0))
            p.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
            p.drawText(qr_rect, Qt.AlignCenter, "[KOD QR HOMEKIT]")

        p.setPen(QColor(0, 0, 0))
        p.setFont(QFont("DejaVu Sans", 12, QFont.Bold))
        p.drawText(QRect(qr_x - 15, qr_y + qr_size - 5, qr_size + 30, 30), Qt.AlignCenter, "APLIKACJA DOM (APPLE)")

    def draw_volume_bar(self, p, w, h):
        box_w = 320
        box_h = 60
        rect = QRect((w - box_w) // 2, 40, box_w, box_h)
        p.setBrush(QBrush(QColor(15, 23, 42, 230)))
        p.setPen(QPen(QColor(14, 165, 233), 2))
        p.drawRoundedRect(rect, 10, 10)

        p.setFont(QFont("DejaVu Sans", 12, QFont.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(rect.x() + 20, rect.y() + 36, f"GŁOŚNOŚĆ: {self.volume}%")

        bar_rect = QRect(rect.x() + 145, rect.y() + 24, 150, 12)
        p.setBrush(QBrush(QColor(30, 41, 59)))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(bar_rect, 4, 4)

        fill_w = int(150 * (self.volume / 100))
        p.setBrush(QBrush(QColor(14, 165, 233)))
        p.drawRoundedRect(QRect(bar_rect.x(), bar_rect.y(), fill_w, 12), 4, 4)

    def draw_dialing_badge(self, p, w, h):
        rect = QRect(w - 180, h - 160, 120, 70)
        p.setBrush(QBrush(QColor(2, 132, 199, 230)))
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawRoundedRect(rect, 12, 12)

        p.setFont(QFont("DejaVu Sans", 28, QFont.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(rect, Qt.AlignCenter, self.dial_buffer)

    def closeEvent(self, event):
        if self.player:
            self.player.stop()
        super().closeEvent(event)

# ==============================================================================
# PUNKT STARTOWY NATYWNEGO PROGRAMU
# ==============================================================================
def main():
    # Uruchomienie serwera API pilota w osobnym wątku
    t_api = threading.Thread(target=start_api_server, daemon=True)
    t_api.start()

    # Uruchomienie mostka Apple TV jeśli dostępny
    apple_script = os.path.join(APP_DIR, "apple_tv_bridge.py")
    if os.path.exists(apple_script):
        try:
            subprocess.Popen([sys.executable, apple_script])
        except Exception:
            pass

    app = QApplication(sys.argv)
    window = TVDecoderNativeWindow()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
