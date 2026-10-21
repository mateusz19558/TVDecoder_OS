#!/usr/bin/env python3
# ==============================================================================
# TVDecoder OS - Pełnoekranowy Ekran Ładowania (Splash Screen) Aurora OS
# Zastępuje wiersz poleceń i logi systemowe eleganckim ekranem startowym
# ==============================================================================

import sys
import os
import time
import urllib.request
import threading

def main():
    try:
        import tkinter as tk
    except ImportError:
        # Fallback jeśli brak tkinter
        sys.exit(0)

    root = tk.Tk()
    root.title("Aurora OS Bootloader")
    
    # Tryb pełnoekranowy bez ramek okna
    root.attributes("-fullscreen", True)
    root.config(cursor="none", bg="#080d1a")
    
    # Rozdzielczość ekranu
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    canvas = tk.Canvas(root, width=sw, height=sh, bg="#080d1a", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # Rysowanie dekoracyjnego blasku w tle (radial glow)
    cx, cy = sw // 2, sh // 2 - 40
    
    # Napis AURORA OS
    canvas.create_text(
        cx - 35, cy - 20,
        text="AURORA",
        fill="#ffffff",
        font=("DejaVu Sans", 38, "bold")
    )
    canvas.create_text(
        cx + 105, cy - 20,
        text="OS",
        fill="#38bdf8",
        font=("DejaVu Sans", 38, "bold")
    )

    # Podtytuł
    canvas.create_text(
        cx, cy + 30,
        text="DEKODER TELEWIZJI CYFROWEJ & SMART TV",
        fill="#94a3b8",
        font=("DejaVu Sans", 11, "bold")
    )

    # Pasek postępu (obramowanie i tło)
    bar_w = 360
    bar_h = 6
    bx1 = cx - bar_w // 2
    by1 = cy + 85
    bx2 = cx + bar_w // 2
    by2 = by1 + bar_h

    canvas.create_rectangle(bx1 - 1, by1 - 1, bx2 + 1, by2 + 1, fill="#1e293b", outline="#334155", width=1)
    progress_bar = canvas.create_rectangle(bx1, by1, bx1, by2, fill="#38bdf8", outline="")

    # Etykieta statusu
    status_text = canvas.create_text(
        cx, by2 + 25,
        text="Uruchamianie systemu Aurora OS...",
        fill="#64748b",
        font=("DejaVu Sans", 10)
    )

    statuses = [
        "Inicjalizacja modułów sprzętowych i kodeków wideo...",
        "Uruchamianie silnika Canal+ RxPlayer i mostka sieciowego...",
        "Synchronizacja kanałów telewizyjnych i przewodnika EPG...",
        "Ładowanie interfejsu użytkownika Aurora Box Pro...",
        "Gotowe. Startowanie odtwarzacza TV..."
    ]

    state = {
        "pct": 5,
        "running": True,
        "step_idx": 0
    }

    def update_animation():
        if not state["running"]:
            return

        state["pct"] = min(98, state["pct"] + 1.2)
        cur_w = int((bar_w * (state["pct"] / 100.0)))
        canvas.coords(progress_bar, bx1, by1, bx1 + cur_w, by2)

        # Zmiana napisów w miarę postępu
        idx = int((state["pct"] / 100.0) * len(statuses))
        idx = min(len(statuses) - 1, idx)
        if idx != state["step_idx"]:
            state["step_idx"] = idx
            canvas.itemconfig(status_text, text=statuses[idx])

        root.after(35, update_animation)

    def check_server_and_chromium():
        # Czekaj na dostępność serwera aplikacji
        start_t = time.time()
        server_ready = False
        while time.time() - start_t < 15:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8080/", timeout=0.4) as resp:
                    if resp.status == 200:
                        server_ready = True
                        break
            except Exception:
                time.sleep(0.2)

        # Daj Chromium moment na zmapowanie okna na pełnym ekranie
        time.sleep(1.2)
        state["running"] = False
        try:
            root.destroy()
        except Exception:
            pass

    t = threading.Thread(target=check_server_and_chromium, daemon=True)
    t.start()

    root.after(30, update_animation)
    root.mainloop()

if __name__ == "__main__":
    main()
