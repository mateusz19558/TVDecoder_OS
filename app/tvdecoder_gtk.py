#!/usr/bin/env python3
# ==============================================================================
# TVDecoder OS - Natywne Okno WebKitGTK / GTK3 (Dla systemów Linux)
# ==============================================================================

import os
import sys

try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('WebKit2', '4.1')
    from gi.repository import Gtk, WebKit2, Gdk, GLib
except Exception as e:
    print(f"[TVDecoder GTK] Błąd ładowania bibliotek PyGObject/WebKitGTK: {e}")
    sys.exit(1)

class TVDecoderGTKWindow(Gtk.Window):
    def __init__(self, url="http://127.0.0.1:8080/"):
        super().__init__(title="TV Decoder")

        # 1. Konfiguracja okna na pełnym ekranie
        self.fullscreen()
        self.set_decorated(False)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key_press)

        # Ukrywanie kursora myszy
        cursor = Gdk.Cursor.new_from_name(self.get_display(), "none")
        if cursor:
            self.get_root_window().set_cursor(cursor)

        # 2. Konfiguracja silnika WebKit2
        settings = WebKit2.Settings()
        settings.set_enable_developer_extras(False)
        settings.set_enable_media_stream(True)
        settings.set_enable_mediasource(True)
        settings.set_enable_webaudio(True)
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)

        self.webview = WebKit2.WebView.new_with_settings(settings)
        self.webview.connect("web-process-terminated", self.on_web_process_crashed)

        self.add(self.webview)
        self.show_all()

        # 3. Załadowanie interfejsu TV
        self.webview.load_uri(url)

    def on_key_press(self, widget, event):
        keyval = event.keyval
        key_name = Gdk.keyval_name(keyval)

        # Mapowanie klawiszy na komendy pilota Aurora
        key_map = {
            "Up": "up",
            "Down": "down",
            "Left": "left",
            "Right": "right",
            "Return": "select",
            "KP_Enter": "select",
            "BackSpace": "back",
            "Escape": "back",
            "m": "exit",
            "M": "exit",
            "space": "play_pause",
            "plus": "vol_up",
            "minus": "vol_down"
        }

        cmd = key_map.get(key_name)
        if cmd:
            js = f"if(window.handleRemoteKey) window.handleRemoteKey('{cmd}');"
            self.webview.run_javascript(js, None, None, None)
            return True

        return False

    def on_web_process_crashed(self, webview, reason):
        print(f"[TVDecoder GTK] Proces renderowania zakończył działanie (powód: {reason}), przeładowuję stronę...")
        GLib.timeout_add_seconds(1, self.webview.reload)

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080/"
    app = TVDecoderGTKWindow(url)
    Gtk.main()

if __name__ == "__main__":
    main()
