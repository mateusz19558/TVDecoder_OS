#!/usr/bin/env python3
# ==============================================================================
# Apple TV / HomeKit Remote Bridge dla TVDecoder
# Umożliwia sterowanie dekoderem za pomocą natywnego Pilota Apple z Centrum Sterowania na iPhone
# ==============================================================================

import sys
import logging
import requests
from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_TELEVISION

logging.basicConfig(level=logging.INFO, format="[AppleRemote] %(message)s")

DECODER_API_URL = "http://127.0.0.1:8080/api/remote"

def send_to_decoder(params):
    try:
        requests.get(DECODER_API_URL, params=params, timeout=0.8)
    except Exception as e:
        logging.debug(f"Błąd wysyłania do dekodera: {e}")

class TVDecoderAccessory(Accessory):
    category = CATEGORY_TELEVISION

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Główna usługa telewizora HomeKit
        tv_service = self.add_preload_service("Television")
        
        # Nazwa wyświetlana w iPhone
        tv_service.configure_char("ConfiguredName", value="TV Decoder")
        tv_service.configure_char("Active", value=1, setter_callback=self.set_active)
        tv_service.configure_char("ActiveIdentifier", value=1, setter_callback=self.set_input)
        tv_service.configure_char("RemoteKey", setter_callback=self.handle_remote_key)
        tv_service.configure_char("SleepDiscoveryMode", value=1)

        # 2. Wejście 1: Telewizja
        input_tv = self.add_preload_service("InputSource", unique_id="input_1")
        input_tv.configure_char("ConfiguredName", value="Telewizja (TV)")
        input_tv.configure_char("InputSourceType", value=3) # TV tuner
        input_tv.configure_char("IsConfigured", value=1)
        input_tv.configure_char("CurrentVisibilityState", value=0)
        input_tv.configure_char("Identifier", value=1)
        tv_service.add_linked_service(input_tv)

        # 3. Wejście 2: YouTube Smart TV
        input_yt = self.add_preload_service("InputSource", unique_id="input_2")
        input_yt.configure_char("ConfiguredName", value="YouTube Smart TV")
        input_yt.configure_char("InputSourceType", value=10) # Application
        input_yt.configure_char("IsConfigured", value=1)
        input_yt.configure_char("CurrentVisibilityState", value=0)
        input_yt.configure_char("Identifier", value=2)
        tv_service.add_linked_service(input_yt)

        # 4. Sterowanie głośnością z fizycznych przycisków iPhone
        speaker = self.add_preload_service("TelevisionSpeaker")
        speaker.configure_char("VolumeControlType", value=1) # Relative
        speaker.configure_char("VolumeSelector", setter_callback=self.handle_volume)
        tv_service.add_linked_service(speaker)

    def set_active(self, value):
        logging.info(f"Zasilanie TV: {value}")
        send_to_decoder({"key": "power" if value == 0 else "tv"})

    def set_input(self, value):
        logging.info(f"Przełączenie wejścia na: {value}")
        send_to_decoder({"input": str(value)})

    def handle_volume(self, value):
        # 0 = Głośniej, 1 = Ciszej
        cmd = "vol_up" if value == 0 else "vol_down"
        logging.info(f"Głośność iPhone: {cmd}")
        send_to_decoder({"key": cmd})

    def handle_remote_key(self, value):
        # Mapowanie klawiszy natywnego Pilota Apple na iPhone:
        key_map = {
            4: "up",         # Strzałka w górę
            5: "down",       # Strzałka w dół
            6: "left",       # Strzałka w lewo
            7: "right",      # Strzałka w prawo
            8: "select",     # Kliknięcie / OK
            9: "back",       # Przycisk Wróć
            10: "exit",      # Przycisk TV / Wyjście (wraca do TV!)
            11: "play_pause",# Play / Pause
            15: "info"       # Informacje o programie
        }
        cmd = key_map.get(value, "select")
        logging.info(f"Klawisz z pilota Apple (kod {value}): {cmd}")
        send_to_decoder({"key": cmd})

def main():
    driver = AccessoryDriver(port=51827, pincode=b"111-22-333")
    accessory = TVDecoderAccessory(driver, "TV Decoder")
    driver.add_accessory(accessory=accessory)
    
    # Generowanie kodu QR dla iPhone
    try:
        import os
        import qrcode
        uri = accessory.xhm_uri()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        qr_file = os.path.join(script_dir, "apple_remote_qr.png")
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_file)
        logging.info(f"Kod QR HomeKit zapisany: {qr_file} (URI: {uri})")
    except Exception as e:
        logging.warning(f"Nie udało się wygenerować pliku QR: {e}")

    logging.info("=================================================================")
    logging.info(" 📱 Mostek Apple TV Remote uruchomiony!")
    logging.info(" Kod parowania w aplikacji Dom (Apple Home): 111-22-333")
    logging.info("=================================================================")
    
    driver.start()

if __name__ == "__main__":
    main()
