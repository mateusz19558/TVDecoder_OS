#!/usr/bin/env python3
# ==============================================================================
# Apple TV / HomeKit Remote & AirPlay 2 Bridge dla TVDecoder (Aurora OS)
# Umożliwia sterowanie dekoderem za pomocą Pilota Apple z Centrum Sterowania na iPhone
# oraz wykrywanie dekodera w menu Klonowania Ekranu (AirPlay 2 Mirroring)
# ==============================================================================

import sys
import os
import socket
import logging
import threading
import plistlib
import requests
import json
import base64
import hashlib

# Zabezpieczenie przed błędem kodowania CP1250 w konsoli Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apple_tv_bridge.log")
logging.basicConfig(
    level=logging.INFO,
    format="[AppleRemote] %(asctime)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, mode="a", encoding="utf-8")
    ]
)

# ==============================================================================
# KLUCZ PRYWATNY AIRPORT EXPRESS RSA I OBLICZANIE APPLE-RESPONSE
# Wymagane przez iPhone przy zapytaniu RTSP OPTIONS z nagłówkiem Apple-Challenge.
# ==============================================================================
AIRPORT_PRIVATE_KEY_PEM = """-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEA59dE8qLieItsH1WgjrcFRKj6eUWqi+bGLOX1HL3U3GhC/j0Qg90u3sG/1CUt
wC5vOYvfDmFI6oSFXi5ELabWJmT2dKHzBJKa3k9ok+8t9ucRqMd6DZHJ2YCCLlDRKSKv6kDqnw4U
wPdpOMXziC/AMj3Z/lUVX1G7WSHCAWKf1zNS1eLvqr+boEjXuBOitnZ/bDzPHrTOZz0Dew0uowxf
/+sG+NCK3eQJVxqcaJ/vEHKIVd2M+5qL71yJQ+87X6oV3eaYvt3zWZYD6z5vYTcrtij2VZ9Zmni/
UAaHqn9JdsBWLUEpVviYnhimNVvYFZeCXg/IdTQ+x4IRdiXNv5hEewIDAQABAoIBAQDl8Axy9XfW
BLmkzkEiqoSwF0PsmVrPzH9KsnwLGH+QZlvjWd8SWYGN7u1507HvhF5N3drJoVU3O14nDY4TFQAa
LlJ9VM35AApXaLyY1ERrN7u9ALKd2LUwYhM7Km539O4yUFYikE2nIPscEsA5ltpxOgUGCY7b7ez5
NtD6nL1ZKauw7aNXmVAvmJTcuPxWmoktF3gDJKK2wxZuNGcJE0uFQEG4Z3BrWP7yoNuSK3dii2jm
lpPHr0O/KnPQtzI3eguhe0TwUem/eYSdyzMyVx/YpwkzwtYL3sR5k0o9rKQLtvLzfAqdBxBurciz
aaA/L0HIgAmOit1GJA2saMxTVPNhAoGBAPfgv1oeZxgxmotiCcMXFEQEWflzhWYTsXrhUIuz5jFu
a39GLS99ZEErhLdrwj8rDDViRVJ5skOp9zFvlYAHs0xh92ji1E7V/ysnKBfsMrPkk5KSKPrnjndM
oPdevWnVkgJ5jxFuNgxkOLMuG9i53B4yMvDTCRiIPMQ++N2iLDaRAoGBAO9v//mU8eVkQaoANf0Z
oMjW8CN4xwWA2cSEIHkd9AfFkftuv8oyLDCG3ZAf0vrhrrtkrfa7ef+AUb69DNggq4mHQAYBp7L+
k5DKzJrKuO0r+R0YbY9pZD1+/g9dVt91d6LQNepUE/yY2PP5CNoFmjedpLHMOPFdVgqDzDFxU8hL
AoGBANDrr7xAJbqBjHVwIzQ4To9pb4BNeqDndk5Qe7fT3+/H1njGaC0/rXE0Qb7q5ySgnsCb3DvA
cJyRM9SJ7OKlGt0FMSdJD5KG0XPIpAVNwgpXXH5MDJg09KHeh0kXo+QA6viFBi21y340NonnEfdf
54PX4ZGS/Xac1UK+pLkBB+zRAoGAf0AY3H3qKS2lMEI4bzEFoHeK3G895pDaK3TFBVmD7fV0Zhov
17fegFPMwOII8MisYm9ZfT2Z0s5Ro3s5rkt+nvLAdfC/PYPKzTLalpGSwomSNYJcB9HNMlmhkGzc
1JnLYT4iyUyx6pcZBmCd8bD0iwY/FzcgNDaUmbX9+XDvRA0CgYEAkE7pIPlE71qvfJQgoA9em0gI
LAuE4Pu13aKiJnfft7hIjbK+5kyb3TysZvoyDnb3HOKvInK7vXbKuU4ISgxB2bB3HcYzQMGsz1qJ
2gG0N5hvJpzwwhbhXqFKA4zaaSrw622wDniAK5MlIE0tIAKKP4yxNGjoD2QYjhBGuhvkWKY=
-----END RSA PRIVATE KEY-----"""

try:
    from cryptography.hazmat.primitives import serialization
    _rsa_key = serialization.load_pem_private_key(AIRPORT_PRIVATE_KEY_PEM.encode('ascii'), password=None)
    _priv_numbers = _rsa_key.private_numbers()
    _RSA_D = _priv_numbers.d
    _RSA_N = _priv_numbers.public_numbers.n
except Exception as _ex:
    logging.warning(f"Nie udało się załadować klucza RSA AirPort: {_ex}")
    _RSA_D = None
    _RSA_N = None

def compute_apple_response(challenge_b64, ip_str, mac_str):
    """
    Oblicza podpis RSA PKCS#1 v1.5 na potrzeby nagłówka Apple-Response.
    Dane: challenge_bytes + ip_bytes (4B) + mac_bytes (6B), uzupełnione do min. 32B.
    """
    if not _RSA_D or not _RSA_N or not challenge_b64:
        return None
    try:
        ch = challenge_b64.strip()
        ch += '=' * ((4 - len(ch) % 4) % 4)
        ch_bytes = base64.b64decode(ch)

        ip_bytes = socket.inet_aton(ip_str)
        mac_clean = mac_str.replace(':', '').replace('-', '')
        mac_bytes = bytes.fromhex(mac_clean)

        data = ch_bytes + ip_bytes + mac_bytes
        if len(data) < 32:
            data = data + b'\x00' * (32 - len(data))

        pad_len = 256 - len(data) - 3
        block = b'\x00\x01' + (b'\xff' * pad_len) + b'\x00' + data

        m_int = int.from_bytes(block, 'big')
        c_int = pow(m_int, _RSA_D, _RSA_N)
        c_bytes = c_int.to_bytes(256, 'big')
        return base64.b64encode(c_bytes).decode('ascii').rstrip('=')
    except Exception as e:
        logging.warning(f"Błąd obliczania Apple-Response: {e}")
        return None

DECODER_API_URL = "http://127.0.0.1:8080/api/remote"
AIRPLAY_START_URL = "http://127.0.0.1:8080/api/airplay/start"
AIRPLAY_STOP_URL = "http://127.0.0.1:8080/api/airplay/stop"

def send_to_decoder(params):
    try:
        requests.get(DECODER_API_URL, params=params, timeout=0.8)
    except Exception as e:
        logging.debug(f"Błąd wysyłania do dekodera: {e}")

def trigger_airplay_start(dev_name="iPhone"):
    def _run():
        try:
            requests.get(AIRPLAY_START_URL, params={"device": dev_name}, timeout=1.5)
        except Exception as e:
            logging.debug(f"Błąd powiadomienia o starcie AirPlay: {e}")
    threading.Thread(target=_run, daemon=True).start()

def trigger_airplay_stop():
    def _run():
        try:
            requests.get(AIRPLAY_STOP_URL, timeout=1.5)
        except Exception as e:
            logging.debug(f"Błąd powiadomienia o stopie AirPlay: {e}")
    threading.Thread(target=_run, daemon=True).start()

try:
    from pyhap.accessory import Accessory
    from pyhap.accessory_driver import AccessoryDriver
    from pyhap.const import CATEGORY_TELEVISION
except ImportError:
    logging.error("Brak pakietu HAP-python (pyhap). Zainstaluj: py -m pip install HAP-python[qrcode]")
    sys.exit(1)

class TVDecoderAccessory(Accessory):
    category = CATEGORY_TELEVISION

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 0. Informacje o urządzeniu widoczne w Apple Home
        info_service = self.get_service("AccessoryInformation")
        if info_service:
            info_service.configure_char("Manufacturer", value="Apple & CANAL+")
            info_service.configure_char("Model", value="Aurora Box Pro 4K")
            info_service.configure_char("Name", value="Aurora Box Pro TV")
            info_service.configure_char("SerialNumber", value="AUR-APPLE-4K-PL")
            info_service.configure_char("FirmwareRevision", value="3.1.5")

        # 1. Główna usługa telewizora HomeKit z charakterystyką RemoteKey
        tv_service = self.add_preload_service("Television", chars=["RemoteKey"])
        tv_service.is_primary_service = True
        tv_service.configure_char("ConfiguredName", value="Aurora Box Pro TV")
        tv_service.configure_char("Active", value=1, setter_callback=self.set_active)
        tv_service.configure_char("ActiveIdentifier", value=1, setter_callback=self.set_input)
        tv_service.configure_char("SleepDiscoveryMode", value=1)
        tv_service.configure_char("RemoteKey", setter_callback=self.handle_remote_key)

        # 2. Wejście 1: Telewizja na żywo (DVB-T2 / IPTV)
        input_tv = self.add_preload_service("InputSource", chars=["Identifier"], unique_id="input_1")
        input_tv.configure_char("ConfiguredName", value="Telewizja na żywo")
        input_tv.configure_char("InputSourceType", value=3) # TV tuner
        input_tv.configure_char("IsConfigured", value=1)
        input_tv.configure_char("CurrentVisibilityState", value=0)
        input_tv.configure_char("Identifier", value=1)
        tv_service.add_linked_service(input_tv)

        # 3. Wejście 2: YouTube Smart TV
        input_yt = self.add_preload_service("InputSource", chars=["Identifier"], unique_id="input_2")
        input_yt.configure_char("ConfiguredName", value="YouTube Smart TV")
        input_yt.configure_char("InputSourceType", value=10) # Application
        input_yt.configure_char("IsConfigured", value=1)
        input_yt.configure_char("CurrentVisibilityState", value=0)
        input_yt.configure_char("Identifier", value=2)
        tv_service.add_linked_service(input_yt)

        # 4. Wejście 3: Apple AirPlay 2 (Klonowanie ekranu)
        input_airplay = self.add_preload_service("InputSource", chars=["Identifier"], unique_id="input_3")
        input_airplay.configure_char("ConfiguredName", value="Apple AirPlay 2")
        input_airplay.configure_char("InputSourceType", value=10) # Application
        input_airplay.configure_char("IsConfigured", value=1)
        input_airplay.configure_char("CurrentVisibilityState", value=0)
        input_airplay.configure_char("Identifier", value=3)
        tv_service.add_linked_service(input_airplay)

        # 5. Sterowanie głośnością z fizycznych przycisków iPhone
        speaker = self.add_preload_service("TelevisionSpeaker", chars=["VolumeControlType", "VolumeSelector", "Active"])
        speaker.configure_char("VolumeControlType", value=1) # Relative
        speaker.configure_char("VolumeSelector", setter_callback=self.handle_volume)
        speaker.configure_char("Active", value=1)
        tv_service.add_linked_service(speaker)

    def set_active(self, value):
        logging.info(f"Zasilanie TV ze strony Apple: {value}")
        send_to_decoder({"key": "power" if value == 0 else "tv"})

    def set_input(self, value):
        logging.info(f"Przełączenie wejścia na: {value}")
        send_to_decoder({"input": str(value)})

    def handle_volume(self, value):
        cmd = "vol_up" if value == 0 else "vol_down"
        logging.info(f"Głośność iPhone: {cmd}")
        send_to_decoder({"key": cmd})

    def handle_remote_key(self, value):
        key_map = {
            4: "up",         # Strzałka w górę
            5: "down",       # Strzałka w dół
            6: "left",       # Strzałka w lewo
            7: "right",      # Strzałka w prawo
            8: "select",     # Kliknięcie / OK
            9: "back",       # Przycisk Wróć (ESC / Menu)
            10: "exit",      # Przycisk TV / Wyjście (wraca do TV)
            11: "play_pause",# Play / Pause
            15: "info"       # Informacje o programie (OSD)
        }
        cmd = key_map.get(value, "select")
        logging.info(f"Klawisz z pilota Apple (kod {value}): {cmd}")
        send_to_decoder({"key": cmd})

def save_qr_codes(accessory, script_dir):
    try:
        import qrcode
        uri = accessory.xhm_uri()
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        paths_to_save = [
            os.path.join(script_dir, "apple_remote_qr.png"),
            os.path.join(script_dir, "bin_publish", "apple_remote_qr.png"),
            os.path.join(script_dir, "bin", "Release", "net10.0-windows", "apple_remote_qr.png")
        ]

        for p in paths_to_save:
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                img.save(p)
            except Exception:
                pass

        logging.info(f"Kod QR HomeKit zapisany pomyślnie. URI: {uri}")
    except Exception as e:
        logging.warning(f"Nie udało się zapisać pliku QR: {e}")

# ==============================================================================
# ODBIORNIK I ROZGŁASZANIE AIRPLAY 2 DLA CENTRUM STEROWANIA (KLONOWANIE EKRANU)
# ==============================================================================
_airplay_lock = threading.Lock()
_airplay_stop_timer = None
_airplay_session_active = False

FP_REPLY_MESSAGE = [
    bytes([0x46,0x50,0x4c,0x59,0x03,0x01,0x02,0x00,0x00,0x00,0x00,0x82,0x02,0x00,0x0f,0x9f,0x3f,0x9e,0x0a,0x25,0x21,0xdb,0xdf,0x31,0x2a,0xb2,0xbf,0xb2,0x9e,0x8d,0x23,0x2b,0x63,0x76,0xa8,0xc8,0x18,0x70,0x1d,0x22,0xae,0x93,0xd8,0x27,0x37,0xfe,0xaf,0x9d,0xb4,0xfd,0xf4,0x1c,0x2d,0xba,0x9d,0x1f,0x49,0xca,0xaa,0xbf,0x65,0x91,0xac,0x1f,0x7b,0xc6,0xf7,0xe0,0x66,0x3d,0x21,0xaf,0xe0,0x15,0x65,0x95,0x3e,0xab,0x81,0xf4,0x18,0xce,0xed,0x09,0x5a,0xdb,0x7c,0x3d,0x0e,0x25,0x49,0x09,0xa7,0x98,0x31,0xd4,0x9c,0x39,0x82,0x97,0x34,0x34,0xfa,0xcb,0x42,0xc6,0x3a,0x1c,0xd9,0x11,0xa6,0xfe,0x94,0x1a,0x8a,0x6d,0x4a,0x74,0x3b,0x46,0xc3,0xa7,0x64,0x9e,0x44,0xc7,0x89,0x55,0xe4,0x9d,0x81,0x55,0x00,0x95,0x49,0xc4,0xe2,0xf7,0xa3,0xf6,0xd5,0xba]),
    bytes([0x46,0x50,0x4c,0x59,0x03,0x01,0x02,0x00,0x00,0x00,0x00,0x82,0x02,0x01,0xcf,0x32,0xa2,0x57,0x14,0xb2,0x52,0x4f,0x8a,0xa0,0xad,0x7a,0xf1,0x64,0xe3,0x7b,0xcf,0x44,0x24,0xe2,0x00,0x04,0x7e,0xfc,0x0a,0xd6,0x7a,0xfc,0xd9,0x5d,0xed,0x1c,0x27,0x30,0xbb,0x59,0x1b,0x96,0x2e,0xd6,0x3a,0x9c,0x4d,0xed,0x88,0xba,0x8f,0xc7,0x8d,0xe6,0x4d,0x91,0xcc,0xfd,0x5c,0x7b,0x56,0xda,0x88,0xe3,0x1f,0x5c,0xce,0xaf,0xc7,0x43,0x19,0x95,0xa0,0x16,0x65,0xa5,0x4e,0x19,0x39,0xd2,0x5b,0x94,0xdb,0x64,0xb9,0xe4,0x5d,0x8d,0x06,0x3e,0x1e,0x6a,0xf0,0x7e,0x96,0x56,0x16,0x2b,0x0e,0xfa,0x40,0x42,0x75,0xea,0x5a,0x44,0xd9,0x59,0x1c,0x72,0x56,0xb9,0xfb,0xe6,0x51,0x38,0x98,0xb8,0x02,0x27,0x72,0x19,0x88,0x57,0x16,0x50,0x94,0x2a,0xd9,0x46,0x68,0x8a]),
    bytes([0x46,0x50,0x4c,0x59,0x03,0x01,0x02,0x00,0x00,0x00,0x00,0x82,0x02,0x02,0xc1,0x69,0xa3,0x52,0xee,0xed,0x35,0xb1,0x8c,0xdd,0x9c,0x58,0xd6,0x4f,0x16,0xc1,0x51,0x9a,0x89,0xeb,0x53,0x17,0xbd,0x0d,0x43,0x36,0xcd,0x68,0xf6,0x38,0xff,0x9d,0x01,0x6a,0x5b,0x52,0xb7,0xfa,0x92,0x16,0xb2,0xb6,0x54,0x82,0xc7,0x84,0x44,0x11,0x81,0x21,0xa2,0xc7,0xfe,0xd8,0x3d,0xb7,0x11,0x9e,0x91,0x82,0xaa,0xd7,0xd1,0x8c,0x70,0x63,0xe2,0xa4,0x57,0x55,0x59,0x10,0xaf,0x9e,0x0e,0xfc,0x76,0x34,0x7d,0x16,0x40,0x43,0x80,0x7f,0x58,0x1e,0xe4,0xfb,0xe4,0x2c,0xa9,0xde,0xdc,0x1b,0x5e,0xb2,0xa3,0xaa,0x3d,0x2e,0xcd,0x59,0xe7,0xee,0xe7,0x0b,0x36,0x29,0xf2,0x2a,0xfd,0x16,0x1d,0x87,0x73,0x53,0xdd,0xb9,0x9a,0xdc,0x8e,0x07,0x00,0x6e,0x56,0xf8,0x50,0xce]),
    bytes([0x46,0x50,0x4c,0x59,0x03,0x01,0x02,0x00,0x00,0x00,0x00,0x82,0x02,0x03,0x90,0x01,0xe1,0x72,0x7e,0x0f,0x57,0xf9,0xf5,0x88,0x0d,0xb1,0x04,0xa6,0x25,0x7a,0x23,0xf5,0xcf,0xff,0x1a,0xbb,0xe1,0xe9,0x30,0x45,0x25,0x1a,0xfb,0x97,0xeb,0x9f,0xc0,0x01,0x1e,0xbe,0x0f,0x3a,0x81,0xdf,0x5b,0x69,0x1d,0x76,0xac,0xb2,0xf7,0xa5,0xc7,0x08,0xe3,0xd3,0x28,0xf5,0x6b,0xb3,0x9d,0xbd,0xe5,0xf2,0x9c,0x8a,0x17,0xf4,0x81,0x48,0x7e,0x3a,0xe8,0x63,0xc6,0x78,0x32,0x54,0x22,0xe6,0xf7,0x8e,0x16,0x6d,0x18,0xaa,0x7f,0xd6,0x36,0x25,0x8b,0xce,0x28,0x72,0x6f,0x66,0x1f,0x73,0x88,0x93,0xce,0x44,0x31,0x1e,0x4b,0xe6,0xc0,0x53,0x51,0x93,0xe5,0xef,0x72,0xe8,0x68,0x62,0x33,0x72,0x9c,0x22,0x7d,0x82,0x0c,0x99,0x94,0x45,0xd8,0x92,0x46,0xc8,0xc3,0x59])
]

FP_HEADER = bytes([0x46, 0x50, 0x4c, 0x59, 0x03, 0x01, 0x04, 0x00, 0x00, 0x00, 0x00, 0x14])

# ==============================================================================
# PROTOKÓŁ TLV8 I PAIR-VERIFY (TRANSIENT) DLA AirPlay 2
# ==============================================================================
# Stałe typów TLV8
_TLV_IDENTIFIER = 0x01
_TLV_PUBKEY = 0x03
_TLV_ENC_DATA = 0x05
_TLV_STATE = 0x06
_TLV_ERROR = 0x07
_TLV_SIGNATURE = 0x0A

def tlv8_decode(data):
    """Dekoduje dane w formacie TLV8 (Type-Length-Value, maks. 255B na fragment)."""
    result = {}
    i = 0
    while i + 1 < len(data):
        t = data[i]
        l = data[i + 1]
        v = data[i + 2: i + 2 + l]
        if t in result:
            result[t] = result[t] + bytes(v)  # konkatenacja fragmentów
        else:
            result[t] = bytes(v)
        i += 2 + l
    return result

def tlv8_encode(entries):
    """Koduje listę krotek (typ, wartość) do formatu TLV8."""
    out = bytearray()
    for t, v in entries:
        v = bytes(v) if not isinstance(v, (bytes, bytearray)) else v
        off = 0
        while off < len(v):
            chunk = v[off:off + 255]
            out.append(t)
            out.append(len(chunk))
            out.extend(chunk)
            off += 255
        if len(v) == 0:
            out.append(t)
            out.append(0)
    return bytes(out)


class AirPlayPairVerify:
    """
    Obsługuje pair-verify w trybie transient dla AirPlay 2.
    W tym trybie KAŻDY klient (iPhone) jest akceptowany bez wymogu
    wcześniejszego sparowania — wystarczy wymiana kluczy Curve25519.
    """

    def __init__(self, ed25519_private_hex, accessory_id):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        self.ed_priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(ed25519_private_hex))
        self.ed_pub = self.ed_priv.public_key()
        self.accessory_id = accessory_id.encode("utf-8") if isinstance(accessory_id, str) else accessory_id
        self.shared = None
        self._session_key = None
        self._x_pub_bytes = None
        self._client_x_pub = None
        self.read_key = None
        self.write_key = None

    def handle_m1(self, body):
        """Przetwarza M1 od klienta i generuje odpowiedź M2."""
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

        tlvs = tlv8_decode(body)
        client_x_pub_bytes = tlvs.get(_TLV_PUBKEY, b'')
        if len(client_x_pub_bytes) != 32:
            logging.warning("[PairVerify] M1: nieprawidłowy klucz publiczny klienta")
            return tlv8_encode([(_TLV_STATE, b'\x02'), (_TLV_ERROR, b'\x02')])

        self._client_x_pub = client_x_pub_bytes

        # Generowanie efemerycznego klucza X25519 (Curve25519)
        x_priv = X25519PrivateKey.generate()
        x_pub = x_priv.public_key()
        self._x_pub_bytes = x_pub.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

        # Obliczenie shared secret (ECDH)
        client_x = X25519PublicKey.from_public_bytes(client_x_pub_bytes)
        self.shared = x_priv.exchange(client_x)

        # Wyprowadzenie klucza sesyjnego do szyfrowania kroków pair-verify
        self._session_key = HKDF(
            algorithm=hashes.SHA512(), length=32,
            salt=b"Pair-Verify-Encrypt-Salt",
            info=b"Pair-Verify-Encrypt-Info"
        ).derive(self.shared)

        # Pobranie klucza publicznego Ed25519 serwera
        ed_pub_bytes = self.ed_pub.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

        # accessoryInfo = server_x25519_pub + accessory_id + client_x25519_pub
        acc_info = self._x_pub_bytes + self.accessory_id + client_x_pub_bytes
        signature = self.ed_priv.sign(acc_info)

        sub_tlv = tlv8_encode([
            (_TLV_IDENTIFIER, self.accessory_id),
            (_TLV_SIGNATURE, signature)
        ])

        # Szyfrowanie ChaCha20-Poly1305
        nonce = b'\x00\x00\x00\x00PV-Msg02'
        cipher = ChaCha20Poly1305(self._session_key)
        encrypted = cipher.encrypt(nonce, sub_tlv, None)

        logging.info(f"[PairVerify] M1->M2 OK: wymiana kluczy Curve25519 zakończona")

        return tlv8_encode([
            (_TLV_STATE, b'\x02'),
            (_TLV_PUBKEY, self._x_pub_bytes),
            (_TLV_ENC_DATA, encrypted)
        ])

    def handle_m3(self, body):
        """Przetwarza M3 od klienta i generuje M4. Zwraca (response, success)."""
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes

        tlvs = tlv8_decode(body)
        enc_data = tlvs.get(_TLV_ENC_DATA, b'')

        # Deszyfrowanie danych klienta
        nonce = b'\x00\x00\x00\x00PV-Msg03'
        cipher = ChaCha20Poly1305(self._session_key)
        try:
            decrypted = cipher.decrypt(nonce, enc_data, None)
        except Exception as e:
            logging.warning(f"[PairVerify] Błąd deszyfrowania M3: {e}")
            return tlv8_encode([(_TLV_STATE, b'\x04'), (_TLV_ERROR, b'\x02')]), False

        # Parsujemy sub-TLV klienta (identifier + signature)
        sub_tlvs = tlv8_decode(decrypted)
        client_id = sub_tlvs.get(_TLV_IDENTIFIER, b'')
        client_sig = sub_tlvs.get(_TLV_SIGNATURE, b'')
        logging.info(f"[PairVerify] M3: klient ID={client_id[:20]}... (tryb transient — akceptuję)")

        # W trybie transient akceptujemy KAŻDEGO klienta bez weryfikacji
        # (nie sprawdzamy paired_clients — to właśnie umożliwia AirPlay bez sparowania)

        # Wyprowadzenie kluczy sesyjnych do szyfrowania RTSP po pair-verify
        self.read_key = HKDF(
            algorithm=hashes.SHA512(), length=32,
            salt=b"Control-Salt",
            info=b"Control-Read-Encryption-Key"
        ).derive(self.shared)

        self.write_key = HKDF(
            algorithm=hashes.SHA512(), length=32,
            salt=b"Control-Salt",
            info=b"Control-Write-Encryption-Key"
        ).derive(self.shared)

        logging.info("[PairVerify] M3->M4 OK: klucze sesyjne RTSP wyprowadzone")
        return tlv8_encode([(_TLV_STATE, b'\x04')]), True


class EncryptedRTSP:
    """
    Warstwa szyfrowania ChaCha20-Poly1305 dla połączenia RTSP po pair-verify.

    Po zakończeniu pair-verify, iOS przełącza kanał kontrolny na szyfrowane ramki:
    [2B LE: długość plaintextu] [zaszyfrowane dane + 16B auth tag]
    AAD = nagłówek 2-bajtowy długości.
    """

    def __init__(self, sock, read_key, write_key):
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        self.sock = sock
        self.r_cipher = ChaCha20Poly1305(read_key)
        self.w_cipher = ChaCha20Poly1305(write_key)
        self.r_cnt = 0
        self.w_cnt = 0

    def _nonce(self, cnt):
        """Tworzy nonce: 4 bajty zer + 8 bajtów little-endian counter."""
        return b'\x00\x00\x00\x00' + cnt.to_bytes(8, 'little')

    def _recv_exact(self, n):
        """Odczytuje dokładnie n bajtów z gniazda."""
        buf = bytearray()
        while len(buf) < n:
            try:
                c = self.sock.recv(min(8192, n - len(buf)))
                if not c:
                    return None
                buf.extend(c)
            except Exception:
                return None
        return bytes(buf)

    def read_message(self):
        """
        Odczytuje i deszyfruje jedną ramkę RTSP.
        Zwraca (method, path, headers, body) lub (None, None, {}, b"") przy błędzie.
        """
        # 2 bajty LE: długość plaintextu
        hdr = self._recv_exact(2)
        if not hdr or len(hdr) < 2:
            return None, None, {}, b""

        length = int.from_bytes(hdr, 'little')
        if length == 0 or length > 131072:
            logging.warning(f"[EncRTSP] Nieprawidłowa długość ramki: {length}")
            return None, None, {}, b""

        # Zaszyfrowane dane = length bajtów + 16 bajtów auth tag
        enc = self._recv_exact(length + 16)
        if not enc:
            return None, None, {}, b""

        try:
            nonce = self._nonce(self.r_cnt)
            self.r_cnt += 1
            plaintext = self.r_cipher.decrypt(nonce, enc, hdr)
        except Exception as e:
            logging.warning(f"[EncRTSP] Błąd deszyfrowania ramki (cnt={self.r_cnt-1}): {e}")
            return None, None, {}, b""

        return self._parse_rtsp(plaintext)

    def send_response(self, data):
        """Szyfruje i wysyła odpowiedź RTSP."""
        if isinstance(data, str):
            data = data.encode('utf-8')

        length = len(data)
        hdr = length.to_bytes(2, 'little')
        nonce = self._nonce(self.w_cnt)
        self.w_cnt += 1
        enc = self.w_cipher.encrypt(nonce, data, hdr)
        self.sock.sendall(hdr + enc)

    @staticmethod
    def _parse_rtsp(data):
        """Parsuje wiadomość RTSP z odszyfrowanych bajtów."""
        # Szukamy separatora nagłówek/body
        sep = data.find(b'\r\n\r\n')
        if sep == -1:
            # Może to nie RTSP — zwracamy jako body
            return "DATA", "/raw", {}, data

        header_bytes = data[:sep]
        body_bytes = data[sep + 4:]

        header_str = header_bytes.decode('utf-8', errors='ignore')
        lines = header_str.splitlines()
        if not lines:
            return None, None, {}, b""

        parts = lines[0].split()
        method = parts[0] if parts else "GET"
        path = parts[1] if len(parts) > 1 else ""

        headers = {}
        for line in lines[1:]:
            if ':' in line:
                k, v = line.split(':', 1)
                headers[k.strip().lower()] = v.strip()

        return method, path, headers, body_bytes


# ==============================================================================
# OBSŁUGA AKTYWNOŚCI I TIMEOUT SESJI AIRPLAY
# ==============================================================================

def on_airplay_activity(client_ip):
    global _airplay_stop_timer, _airplay_session_active
    with _airplay_lock:
        if _airplay_stop_timer is not None:
            _airplay_stop_timer.cancel()
            _airplay_stop_timer = None
        if not _airplay_session_active:
            _airplay_session_active = True
            logging.info(f"[AirPlay] Aktywacja sesji projekcji dla {client_ip}")
            trigger_airplay_start(f"iPhone ({client_ip})")

def schedule_airplay_stop():
    global _airplay_stop_timer
    with _airplay_lock:
        if _airplay_stop_timer is not None:
            _airplay_stop_timer.cancel()
        # 6 sekund bufora na renegocjację lub kolejne połączenie ze strony iOS
        _airplay_stop_timer = threading.Timer(6.0, _do_airplay_stop)
        _airplay_stop_timer.daemon = True
        _airplay_stop_timer.start()

def _do_airplay_stop():
    global _airplay_stop_timer, _airplay_session_active
    with _airplay_lock:
        _airplay_stop_timer = None
        _airplay_session_active = False
    logging.info("[AirPlay] Brak aktywności ze strony iPhone - zakończenie projekcji.")
    trigger_airplay_stop()

def immediate_airplay_stop():
    global _airplay_stop_timer, _airplay_session_active
    with _airplay_lock:
        if _airplay_stop_timer is not None:
            _airplay_stop_timer.cancel()
            _airplay_stop_timer = None
        _airplay_session_active = False
    logging.info("[AirPlay] Natychmiastowe zakończenie projekcji (TEARDOWN).")
    trigger_airplay_stop()


# ==============================================================================
# PARSOWANIE I NASŁUCHIWANIE RTSP
# ==============================================================================

def read_http_message(sock):
    """Odczytuje kompletne żądanie HTTP/RTSP z uwzględnieniem Content-Length."""
    buf = bytearray()
    while b"\r\n\r\n" not in buf:
        try:
            chunk = sock.recv(2048)
            if not chunk:
                return None, None, {}, b""
            buf.extend(chunk)
            if len(buf) > 65536:
                break
        except Exception:
            return None, None, {}, b""

    header_end = buf.find(b"\r\n\r\n")
    if header_end == -1:
        return None, None, {}, b""

    header_bytes = bytes(buf[:header_end])
    body_part = bytes(buf[header_end + 4:])

    header_str = header_bytes.decode("utf-8", errors="ignore")
    lines = header_str.splitlines()
    if not lines:
        return None, None, {}, b""

    first_line_parts = lines[0].split()
    method = first_line_parts[0] if len(first_line_parts) > 0 else "GET"
    path = first_line_parts[1] if len(first_line_parts) > 1 else ""

    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    content_length = 0
    try:
        content_length = int(headers.get("content-length", 0))
    except Exception:
        content_length = 0

    body = bytearray(body_part)
    while len(body) < content_length:
        needed = content_length - len(body)
        try:
            chunk = sock.recv(min(4096, needed))
            if not chunk:
                break
            body.extend(chunk)
        except Exception:
            break

    return method, path, headers, bytes(body)

def start_stream_sink_listeners():
    """Uruchamia odbiorniki strumieni danych (wideo 7011, audio 7012, timing 7010)."""
    def tcp_video_sink():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", 7011))
            sock.listen(5)
            while True:
                cli, _ = sock.accept()
                def drain(s):
                    try:
                        while True:
                            b = s.recv(16384)
                            if not b:
                                break
                    except Exception:
                        pass
                    finally:
                        try:
                            s.close()
                        except Exception:
                            pass
                threading.Thread(target=drain, args=(cli,), daemon=True).start()
        except Exception as e:
            logging.debug(f"Video sink bind error: {e}")

    def udp_sink(port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            while True:
                data, _ = sock.recvfrom(4096)
        except Exception as e:
            logging.debug(f"UDP sink {port} bind error: {e}")

    threading.Thread(target=tcp_video_sink, daemon=True).start()
    for p in (7010, 7012, 7013):
        threading.Thread(target=udp_sink, args=(p,), daemon=True).start()


# ==============================================================================
# GŁÓWNY SERWER AIRPLAY RTSP (PORT 7000) Z SZYFROWANYM KANAŁEM
# ==============================================================================

# Flagi AirPlay features dla standardowego screen mirroringu (UxPlay / Apple TV 3):
AIRPLAY_FEATURES = 0x5A7FFFF7
AIRPLAY_FEATURES_STR = '0x5A7FFFF7,0x1E'
STATUS_FLAGS = 68  # 0x44: gotowość i obsługa projekcji ekranu

def get_airplay_desc(mac_addr, pub_key_hex):
    return {
        'acl': '0',
        'deviceid': mac_addr,
        'features': AIRPLAY_FEATURES_STR,
        'flags': '0x4',
        'model': 'AppleTV3,2',
        'pi': '2e388006-13ba-4041-9a67-25b1a4a48451',
        'pk': pub_key_hex,
        'psi': '00000000-0000-0000-0000-000000000000',
        'pw': 'false',
        'srcvers': '220.68',
        'vv': '2'
    }

def get_raop_desc(mac_addr, pub_key_hex):
    return {
        'am': 'AppleTV3,2',
        'cn': '0,1,2,3',        # obsługiwane kodeki (PCM, ALAC, AAC, AAC-ELD)
        'da': 'true',
        'et': '0,3,5',          # typy szyfrowania (none, FairPlay, MFi-SAP)
        'ft': AIRPLAY_FEATURES_STR,
        'md': '0,1,2',          # obsługiwane metadane (text, artwork, progress)
        'pk': pub_key_hex,
        'pw': 'false',
        'sf': '0x4',
        'sr': '44100',          # sample rate
        'ss': '16',             # sample size
        'sv': 'false',
        'tp': 'UDP',
        'vn': '65537',
        'vs': '220.68',
        'vv': '2'
    }

def encode_dnssd_txt(d):
    """Koduje słownik do binarnego formatu rekordów DNS-SD TXT (dla qualifiera POST /info)."""
    buf = bytearray()
    for k, v in d.items():
        entry = f"{k}={v}".encode('utf-8')
        if len(entry) < 256:
            buf.append(len(entry))
            buf.extend(entry)
    return bytes(buf)

def make_challenge_headers(req_headers, lip, mac):
    """Jeśli klient przysłał Apple-Challenge, dołącza podpis Apple-Response i status jacka."""
    ch = req_headers.get("apple-challenge")
    if not ch:
        return ""
    resp_sig = compute_apple_response(ch, lip, mac)
    extra = ""
    if resp_sig:
        extra += f"Apple-Response: {resp_sig}\r\n"
    extra += "Audio-Jack-Status: connected; type=analog\r\n"
    return extra

def start_airplay_listener(local_ip, mac_addr, pub_key_hex, ed_key_hex):
    """Uruchamia serwer RTSP AirPlay na porcie 7000 z obsługą pair-verify i szyfrowania."""

    def listener_thread():
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind(("0.0.0.0", 7000))
            server_sock.listen(5)
            logging.info("Odbiornik połączeń AirPlay nasłuchuje na porcie 7000...")
            while True:
                client, addr = server_sock.accept()
                client_ip = addr[0]

                def handle_client(c, ip):
                    pair_verifier = None
                    enc_rtsp = None  # EncryptedRTSP — ustawiany po pair-verify jeśli TLV8

                    def send_raw(data):
                        """Wysyła dane — przez szyfrowany kanał jeśli aktywny, inaczej plaintext."""
                        if isinstance(data, str):
                            data = data.encode('utf-8')
                        if enc_rtsp:
                            enc_rtsp.send_response(data)
                        else:
                            c.sendall(data)

                    def send_rtsp(status, cseq_val, ct=None, body_data=b"", extra="", req_headers=None):
                        """Buduje i wysyła kompletną odpowiedź RTSP."""
                        resp = f"RTSP/1.0 {status}\r\nServer: AirTunes/220.68\r\nCSeq: {cseq_val}\r\n"
                        if req_headers:
                            resp += make_challenge_headers(req_headers, local_ip, mac_addr)
                        if extra:
                            resp += extra
                        if ct:
                            resp += f"Content-Type: {ct}\r\n"
                        resp += f"Content-Length: {len(body_data)}\r\n\r\n"
                        send_raw(resp.encode('utf-8') + body_data)

                    try:
                        c.settimeout(60.0)
                        while True:
                            # Odczyt wiadomości — szyfrowany lub plaintext
                            if enc_rtsp:
                                method, path, headers, body = enc_rtsp.read_message()
                            else:
                                method, path, headers, body = read_http_message(c)

                            if not method:
                                break

                            on_airplay_activity(ip)

                            cseq = headers.get("cseq", "1")
                            enc_marker = "ENC" if enc_rtsp else "RAW"
                            logging.info(f"[AirPlay/{enc_marker}] {method} {path} (CSeq: {cseq}, Len: {len(body)})")

                            # ==========================================================
                            # 1. Informacje o odbiorniku (/info, /server-info)
                            #    iOS 15+ wysyła zarówno GET jak i POST z qualifierami
                            # ==========================================================
                            if method in ("GET", "POST") and ("/info" in path or "/server-info" in path):
                                plist_dict = {
                                    "deviceid": mac_addr,
                                    "features": AIRPLAY_FEATURES,
                                    "model": "AppleTV3,2",
                                    "protovers": "1.1",
                                    "srcvers": "220.68",
                                    "statusFlags": STATUS_FLAGS,
                                    "pi": "2e388006-13ba-4041-9a67-25b1a4a48451",
                                    "pk": bytes.fromhex(pub_key_hex),
                                    "name": "Aurora Box Pro TV",
                                    "keepAliveLowPower": True,
                                    "macAddress": mac_addr,
                                    "vv": 2,
                                    "displays": [
                                        {
                                            "features": 14,
                                            "height": 1080,
                                            "heightPhysical": 0,
                                            "heightPixels": 1080,
                                            "maxFPS": 60,
                                            "overscanned": False,
                                            "refreshRate": 1.0 / 60.0,
                                            "rotation": False,
                                            "uuid": "2e388006-13ba-4041-9a67-25b1a4a48451",
                                            "width": 1920,
                                            "widthPhysical": 0,
                                            "widthPixels": 1920
                                        }
                                    ],
                                    "audioLatencies": [
                                        {"audioType": "default", "type": 100, "rtpOffset": 11025},
                                        {"audioType": "media", "type": 101, "rtpOffset": 88200},
                                        {"audioType": "telephony", "type": 102, "rtpOffset": 4410}
                                    ],
                                    "audioFormats": [
                                        {"audioInputFormats": 67108860, "audioOutputFormats": 67108860, "type": 100},
                                        {"audioInputFormats": 67108860, "audioOutputFormats": 67108860, "type": 101}
                                    ]
                                }

                                qualifiers = []
                                if body:
                                    try:
                                        req_plist = plistlib.loads(body)
                                        if isinstance(req_plist, dict):
                                            qualifiers = req_plist.get("qualifier", [])
                                        logging.info(f"[AirPlay] {method} /info qualifier: {qualifiers}")
                                    except Exception as ex:
                                        logging.debug(f"[AirPlay] Blad parsowania body /info: {ex}")

                                if qualifiers and any(q in ("txtAirPlay", "txtRAOP") for q in qualifiers):
                                    res_dict = {}
                                    for q in qualifiers:
                                        if q == "txtAirPlay":
                                            res_dict["txtAirPlay"] = encode_dnssd_txt(get_airplay_desc(mac_addr, pub_key_hex))
                                        elif q == "txtRAOP":
                                            res_dict["txtRAOP"] = encode_dnssd_txt(get_raop_desc(mac_addr, pub_key_hex))
                                else:
                                    res_dict = plist_dict

                                req_ct = headers.get("content-type", "")
                                body_bytes = plistlib.dumps(res_dict, fmt=plistlib.FMT_BINARY)
                                res_ct = "application/x-apple-binary-plist"

                                send_rtsp("200 OK", cseq, res_ct, body_bytes, req_headers=headers)

                            # ==========================================================
                            # 2. PAIR-VERIFY — obsługa obu formatów (binarny 68B i TLV8)
                            # ==========================================================
                            elif "/pair-verify" in path:
                                if len(body) == 68:
                                    # Binarny pair-verify (standardowy AirPlay Screen Mirroring)
                                    if body[:4] == b'\x01\x00\x00\x00':
                                        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
                                        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
                                        from cryptography.hazmat.primitives import serialization
                                        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

                                        client_curve_pub = body[4:36]
                                        server_x_priv = X25519PrivateKey.generate()
                                        server_x_pub = server_x_priv.public_key().public_bytes(
                                            serialization.Encoding.Raw, serialization.PublicFormat.Raw
                                        )
                                        shared_secret = server_x_priv.exchange(X25519PublicKey.from_public_bytes(client_curve_pub))

                                        aes_key = hashlib.sha512(b"Pair-Verify-AES-Key" + shared_secret).digest()[:16]
                                        aes_iv = hashlib.sha512(b"Pair-Verify-AES-IV" + shared_secret).digest()[:16]

                                        server_ed_priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(ed_key_hex))
                                        data_to_sign = server_x_pub + client_curve_pub
                                        signature = server_ed_priv.sign(data_to_sign)

                                        cipher = Cipher(algorithms.AES(aes_key), modes.CTR(aes_iv))
                                        encryptor = cipher.encryptor()
                                        enc_sig = encryptor.update(signature)

                                        reply_96 = server_x_pub + enc_sig
                                        send_rtsp("200 OK", cseq, "application/octet-stream", reply_96, req_headers=headers)
                                        logging.info(f"[AirPlay -> PairVerify Binary Krok 1 OK] 68B -> 96B (CSeq:{cseq})")
                                    else:
                                        # Krok 2: Potwierdzenie gotowości do transmisji
                                        send_rtsp("200 OK", cseq, "application/octet-stream", b"", req_headers=headers)
                                        logging.info(f"[AirPlay -> PairVerify Binary Krok 2 OK] handshake zakonczony (CSeq:{cseq})")
                                else:
                                    # Fallback: TLV8 HomeKit Pair-Verify
                                    tlvs = tlv8_decode(body)
                                    state_val = tlvs.get(_TLV_STATE, b'\x00')[0] if _TLV_STATE in tlvs else 0

                                    if state_val == 1:  # M1 -> M2
                                        pair_verifier = AirPlayPairVerify(ed_key_hex, mac_addr)
                                        resp_tlv = pair_verifier.handle_m1(body)
                                        send_rtsp("200 OK", cseq, "application/octet-stream", resp_tlv, req_headers=headers)
                                        logging.info(f"[AirPlay] Pair-verify M1->M2 wyslano (CSeq:{cseq})")

                                    elif state_val == 3:  # M3 -> M4
                                        if pair_verifier is None:
                                            logging.warning("[AirPlay] M3 bez wczesniejszego M1!")
                                            send_rtsp("500 Internal Server Error", cseq, req_headers=headers)
                                            continue

                                        resp_tlv, success = pair_verifier.handle_m3(body)
                                        send_rtsp("200 OK", cseq, "application/octet-stream", resp_tlv, req_headers=headers)

                                        if success:
                                            logging.info("[AirPlay] [OK] Pair-verify zakonczony! Przelaczam na szyfrowany RTSP.")
                                            enc_rtsp = EncryptedRTSP(c, pair_verifier.read_key, pair_verifier.write_key)
                                        else:
                                            logging.warning("[AirPlay] [ERR] Pair-verify M3 zakonczony niepowodzeniem.")
                                    else:
                                        send_rtsp("200 OK", cseq, "application/octet-stream", b"", req_headers=headers)

                            # ==========================================================
                            # 2b. PAIR-SETUP — obsługa binarnego klucza 32B (AirPlay Mirroring)
                            # ==========================================================
                            elif "/pair-setup" in path:
                                if len(body) == 32:
                                    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
                                    from cryptography.hazmat.primitives import serialization
                                    server_ed_priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(ed_key_hex))
                                    server_ed_pub_bytes = server_ed_priv.public_key().public_bytes(
                                        serialization.Encoding.Raw, serialization.PublicFormat.Raw
                                    )
                                    send_rtsp("200 OK", cseq, "application/octet-stream", server_ed_pub_bytes, req_headers=headers)
                                    logging.info(f"[AirPlay -> PAIR-SETUP OK] Wymiana klucza 32B (CSeq:{cseq})")
                                else:
                                    err_tlv = tlv8_encode([
                                        (_TLV_STATE, b'\x02'),
                                        (_TLV_ERROR, b'\x06')  # kTLVError_Unavailable
                                    ])
                                    send_rtsp("200 OK", cseq, "application/pairing+tlv8", err_tlv, req_headers=headers)

                            # ==========================================================
                            # 2c. PAIRINGS — zarzadzanie sparowaniami
                            # ==========================================================
                            elif "/pairings" in path:
                                send_rtsp("200 OK", cseq, "application/pairing+tlv8", b"", req_headers=headers)

                            # ==========================================================
                            # 3. FairPlay Setup (FPLY Handshake)
                            # ==========================================================
                            elif "/fp-setup" in path:
                                if len(body) == 16:
                                    mode = body[14] if len(body) > 14 and body[14] < 4 else 0
                                    res_payload = FP_REPLY_MESSAGE[mode]
                                elif len(body) == 164:
                                    res_payload = FP_HEADER + body[144:164]
                                else:
                                    res_payload = FP_REPLY_MESSAGE[0]

                                send_rtsp("200 OK", cseq, "application/octet-stream", res_payload, req_headers=headers)
                                logging.info(f"[AirPlay -> FP-SETUP OK] FPLY ({len(res_payload)}B, CSeq:{cseq})")

                            # ==========================================================
                            # 4. Negocjacja RTSP OPTIONS
                            # ==========================================================
                            elif method == "OPTIONS":
                                challenge_extra = make_challenge_headers(headers, local_ip, mac_addr)
                                resp = (
                                    f"RTSP/1.0 200 OK\r\n"
                                    f"Server: AirTunes/220.68\r\n"
                                    f"CSeq: {cseq}\r\n"
                                    f"{challenge_extra}"
                                    f"Public: POST, GET, OPTIONS, ANNOUNCE, SETUP, RECORD, PAUSE, FLUSH, TEARDOWN, SETPEERS, INFO, FEEDBACK, GET_PARAMETER, SET_PARAMETER\r\n\r\n"
                                )
                                send_raw(resp)

                            # ==========================================================
                            # 4b. Heartbeat / feedback — iOS odpytuje cyklicznie
                            # ==========================================================
                            elif method == "POST" and "/feedback" in path:
                                send_rtsp("200 OK", cseq, req_headers=headers)

                            # ==========================================================
                            # 5. Konfiguracja strumienia RTSP SETUP
                            # ==========================================================
                            elif method == "SETUP":
                                req_streams = []
                                try:
                                    if body:
                                        req_plist = plistlib.loads(body)
                                        req_streams = req_plist.get("streams", [])
                                        logging.info(f"[AirPlay -> SETUP REQ] Strumieni: {len(req_streams)}")
                                except Exception as ex:
                                    logging.debug(f"[AirPlay SETUP parse error]: {ex}")

                                res_streams = []
                                for s in req_streams:
                                    stype = s.get("type")
                                    if stype == 110:
                                        s_resp = {"type": 110, "dataPort": 7011}
                                        if "streamConnectionID" in s:
                                            s_resp["streamConnectionID"] = s["streamConnectionID"]
                                        res_streams.append(s_resp)
                                    elif stype == 96:
                                        s_resp = {"type": 96, "dataPort": 7012, "controlPort": 7013}
                                        if "streamConnectionID" in s:
                                            s_resp["streamConnectionID"] = s["streamConnectionID"]
                                        res_streams.append(s_resp)

                                if not res_streams:
                                    res_streams = [
                                        {"type": 110, "dataPort": 7011},
                                        {"type": 96, "dataPort": 7012, "controlPort": 7013}
                                    ]

                                res_dict = {
                                    "streams": res_streams,
                                    "timingPort": 7010,
                                    "eventPort": 7000
                                }
                                res_bytes = plistlib.dumps(res_dict, fmt=plistlib.FMT_BINARY)
                                send_rtsp("200 OK", cseq, "application/x-apple-binary-plist", res_bytes,
                                          extra="Session: 1\r\n", req_headers=headers)
                                logging.info(f"[AirPlay -> SETUP OK] wideo:7011, audio:7012 (CSeq:{cseq})")

                            # ==========================================================
                            # 6. Rozpoczecie projekcji RTSP RECORD
                            # ==========================================================
                            elif method == "RECORD":
                                send_rtsp("200 OK", cseq, extra="Session: 1\r\nAudio-Latency: 0\r\n", req_headers=headers)
                                logging.info(f"[AirPlay -> RECORD OK] Projekcja ekranu rozpoczeta! (CSeq:{cseq})")

                            # ==========================================================
                            # 7. Parametry odtwarzania (GET_PARAMETER / SET_PARAMETER)
                            # ==========================================================
                            elif method in ("GET_PARAMETER", "SET_PARAMETER"):
                                send_rtsp("200 OK", cseq, "text/parameters", req_headers=headers)

                            # ==========================================================
                            # 8. Informacje o stanie odtwarzania
                            # ==========================================================
                            elif "/playback-info" in path:
                                pinfo = {
                                    "duration": 0.0,
                                    "position": 0.0,
                                    "playbackBufferEmpty": True,
                                    "playbackBufferFull": False,
                                    "playbackLikelyToKeepUp": True,
                                    "readyToPlay": True
                                }
                                body_p = plistlib.dumps(pinfo, fmt=plistlib.FMT_XML)
                                send_rtsp("200 OK", cseq, "text/x-apple-plist+xml", body_p,
                                          extra="Session: 1\r\n", req_headers=headers)

                            # ==========================================================
                            # 9. Zakonczenie projekcji RTSP TEARDOWN
                            # ==========================================================
                            elif method == "TEARDOWN":
                                send_rtsp("200 OK", cseq, extra="Session: 1\r\n", req_headers=headers)
                                immediate_airplay_stop()
                                break

                            # ==========================================================
                            # 10. Pozostale zapytania (announce, setpeers, itp.)
                            # ==========================================================
                            else:
                                send_rtsp("200 OK", cseq, extra="Session: 1\r\n", req_headers=headers)

                    except Exception as e:
                        logging.info(f"[AirPlay Client Error] {ip}: {e}")
                    finally:
                        try:
                            c.close()
                        except Exception:
                            pass
                        schedule_airplay_stop()

                threading.Thread(target=handle_client, args=(client, client_ip), daemon=True).start()
        except Exception as e:
            logging.warning(f"Blad serwera AirPlay port 7000: {e}")

    t = threading.Thread(target=listener_thread, daemon=True)
    t.start()

def register_airplay_mdns(local_ip, mac_addr, pub_key_hex):
    try:
        from zeroconf import Zeroconf, ServiceInfo
        zc = Zeroconf()
        ip_bytes = socket.inet_aton(local_ip)

        mac_clean = mac_addr.replace(':', '').replace('-', '')
        server_host = f"AuroraBoxPro-{mac_clean[-6:]}.local."

        # 1. Usługa _airplay._tcp — wykrywanie AirPlay w Centrum Sterowania
        airplay_desc = get_airplay_desc(mac_addr, pub_key_hex)
        airplay_info = ServiceInfo(
            '_airplay._tcp.local.',
            'Aurora Box Pro TV._airplay._tcp.local.',
            addresses=[ip_bytes],
            port=7000,
            properties=airplay_desc,
            server=server_host
        )
        zc.register_service(airplay_info)
        logging.info(f"Usluga AirPlay mDNS zarejestrowana (_airplay._tcp.local. port 7000) [features={AIRPLAY_FEATURES_STR}, pw=false]!")

        # 2. Usługa _raop._tcp — WYMAGANA przez iOS do negocjacji strumieni!
        raop_desc = get_raop_desc(mac_addr, pub_key_hex)
        raop_info = ServiceInfo(
            '_raop._tcp.local.',
            f'{mac_clean}@Aurora Box Pro TV._raop._tcp.local.',
            addresses=[ip_bytes],
            port=7000,
            properties=raop_desc,
            server=server_host
        )
        zc.register_service(raop_info)
        logging.info(f"Usluga RAOP mDNS zarejestrowana (_raop._tcp.local. port 7000)!")

        return zc, [airplay_info, raop_info]
    except Exception as e:
        logging.warning(f"Blad rejestracji mDNS AirPlay: {e}")
        return None, None

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    state_file = os.path.join(script_dir, "accessory.state")

    # Obsługa resetowania parowania
    if "--reset" in sys.argv:
        if os.path.exists(state_file):
            try:
                os.remove(state_file)
                logging.info("Usunięto stary plik stanu parowania accessory.state.")
            except Exception as e:
                logging.warning(f"Błąd usuwania accessory.state: {e}")

    try:
        from pyhap import util
        local_ip = util.get_local_address()
    except Exception:
        local_ip = "192.168.0.220"

    driver = AccessoryDriver(
        address=local_ip,
        listen_address="0.0.0.0",
        port=51827,
        pincode=b"111-22-333",
        persist_file=state_file
    )
    driver.state.setup_id = "AUR1"
    accessory = TVDecoderAccessory(driver, "Aurora Box Pro TV")
    driver.add_accessory(accessory=accessory)

    # Pobieramy tożsamość kryptograficzną z drivera pyhap
    mac_addr = driver.state.mac
    try:
        from cryptography.hazmat.primitives import serialization
        pub_key_bytes = driver.state.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        pub_key_hex = pub_key_bytes.hex()
    except Exception:
        pub_key_hex = "8ad061214894862379677f06034110088a347a10221a479b76444bda5990bd2d"

    # Odczyt klucza prywatnego Ed25519 do pair-verify AirPlay
    ed_key_hex = None
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state_data = json.load(f)
            ed_key_hex = state_data.get("private_key")
    except Exception as e:
        logging.warning(f"Nie udało się odczytać klucza prywatnego z accessory.state: {e}")

    if not ed_key_hex:
        # Fallback: generujemy nowy klucz Ed25519 (pair-verify będzie działać, ale tożsamość się zmieni)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization as ser
        tmp_key = Ed25519PrivateKey.generate()
        ed_key_hex = tmp_key.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption()).hex()
        logging.warning("Wygenerowano tymczasowy klucz Ed25519 — pair-verify może wymagać ponownego połączenia")

    logging.info(f"Parametry mostka: MAC={mac_addr}, PubKey={pub_key_hex[:16]}...")
    
    # Generowanie kodu QR dla iPhone
    save_qr_codes(accessory, script_dir)

    # Uruchomienie listenerów portów danych (wideo 7011, audio 7012, timing 7010)
    start_stream_sink_listeners()

    # Uruchomienie mDNS i odbiornika AirPlay (Klonowanie ekranu port 7000)
    start_airplay_listener(local_ip, mac_addr, pub_key_hex, ed_key_hex)
    zc_airplay, info_airplay_list = register_airplay_mdns(local_ip, mac_addr, pub_key_hex)

    logging.info("=================================================================")
    logging.info(" [OK] Mostek Apple TV Remote & AirPlay 2 uruchomiony pomyślnie!")
    logging.info(f" IP lokalny: {local_ip} (MAC: {mac_addr})")
    logging.info(" HomeKit HAP: Port 51827 (PIN: 111-22-333) -> Aplikacja Dom & Pilot iOS")
    logging.info(" AirPlay 2 Mirroring: Port 7000 -> Centrum Sterowania (Klonowanie ekranu)")
    logging.info(" RAOP (Audio): Port 7000 -> Strumieniowanie audio AirPlay")
    logging.info(" Pair-Verify: tryb transient (każdy iPhone akceptowany)")
    logging.info(" Szyfrowanie RTSP: ChaCha20-Poly1305 po pair-verify")
    logging.info("=================================================================")
    
    import signal
    shutdown_event = threading.Event()

    def _on_shutdown(signum, frame):
        logging.info(f"Otrzymano sygnał {signum} — zamykanie mostka...")
        shutdown_event.set()
        try:
            driver.stop()
        except Exception:
            pass

    signal.signal(signal.SIGINT, _on_shutdown)
    signal.signal(signal.SIGTERM, _on_shutdown)

    # Uruchomienie HAP driver w osobnym wątku — driver.start() blokuje,
    # ale w niektórych środowiskach (non-interactive) może wyjść natychmiast
    def _run_driver():
        try:
            driver.start()
        except Exception as e:
            logging.warning(f"HAP driver zakończył się: {e}")

    driver_thread = threading.Thread(target=_run_driver, daemon=True)
    driver_thread.start()

    # Keep-alive: czekaj na sygnał zamknięcia lub zakończenie driver thread
    logging.info("Mostek działa. Naciśnij Ctrl+C aby zakończyć.")
    try:
        while not shutdown_event.is_set():
            # Sprawdzamy co 2 sekundy czy driver thread jeszcze żyje
            driver_thread.join(timeout=2.0)
            if not driver_thread.is_alive() and not shutdown_event.is_set():
                logging.info("HAP driver zakończył się — utrzymuję AirPlay i RAOP...")
                # Nawet jeśli HAP driver padł, AirPlay listener dalej działa
                shutdown_event.wait()  # czekaj na Ctrl+C
    except KeyboardInterrupt:
        logging.info("Ctrl+C — zamykanie...")
    finally:
        if zc_airplay and info_airplay_list:
            try:
                for svc_info in info_airplay_list:
                    zc_airplay.unregister_service(svc_info)
                zc_airplay.close()
            except Exception:
                pass
        logging.info("Mostek zamknięty.")

if __name__ == "__main__":
    main()
