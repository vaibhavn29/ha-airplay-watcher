#!/usr/bin/env python3
"""
AirPlay Watcher - Monitors mDNS for AirPlay playback state
and triggers Home Assistant webhooks.
"""

import os
import time
import logging
import requests
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("airplay-watcher")

# Config from environment (set in add-on options)
HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123")
WEBHOOK_PLAYING = os.environ.get("WEBHOOK_PLAYING", "")
WEBHOOK_IDLE = os.environ.get("WEBHOOK_IDLE", "")
_raw_device_ip = os.environ.get("DEVICE_IP", "").strip()


def _normalize_device_ip(value: str) -> str:
    """Extract plain IP/host from device_ip (strip URL scheme or path if present)."""
    if not value:
        return ""
    s = value.strip()
    for prefix in ("http://", "https://"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    if "/" in s:
        s = s.split("/", 1)[0]
    if ":" in s and not s.startswith("["):
        s = s.split(":")[0]
    return s.strip() or ""


DEVICE_IP = _normalize_device_ip(_raw_device_ip)

# Track last state to avoid duplicate triggers
last_state = None          # None = not yet initialized
last_state_initialized = False


def call_webhook(url):
    if not url:
        log.warning("Webhook URL not configured, skipping.")
        return
    try:
        r = requests.post(url, timeout=5)
        log.info(f"Webhook called: {url} → {r.status_code}")
    except Exception as e:
        log.error(f"Webhook call failed: {e}")


def parse_status_flags(properties: dict) -> bool:
    """Return True if device is actively streaming.

    Observed values from Belkin Soundform:
      0x404 = bit 0x4 set, bit 0x800 NOT set = actively streaming
      0xc04 = bit 0x4 set, bit 0x800 set     = idle/standby

    Bit 0x4   = active AirPlay session
    Bit 0x800 = standby/group-idle (negates active session)
    """
    sf = properties.get(b'sf', properties.get('sf', None))
    if sf is None:
        return False
    try:
        sf_str = sf if isinstance(sf, str) else sf.decode()
        val = int(sf_str, 16) if sf_str.lower().startswith('0x') else int(sf_str)
        log.info(f"  sf raw: {sf_str} → parsed: {val:#x}")
        return bool(val & 0x4) and not bool(val & 0x800)
    except (ValueError, AttributeError):
        return False


def on_service_state_change(zeroconf, service_type, name, state_change):
    global last_state, last_state_initialized

    # Only use RAOP record — it's the authoritative audio stream indicator
    if "_airplay._tcp" in service_type:
        return

    if state_change not in (ServiceStateChange.Added, ServiceStateChange.Updated):
        return

    # get_service_info can return None if the record isn't ready yet
    info = None
    for _ in range(3):
        info = zeroconf.get_service_info(service_type, name)
        if info is not None:
            break
        time.sleep(0.2)
    if info is None:
        log.debug(f"Could not get service info for {name}, skipping.")
        return

    # Filter by device IP if configured
    if DEVICE_IP:
        addresses = info.parsed_addresses()
        if DEVICE_IP not in addresses:
            return

    log.info(f"Service update: {name}")
    log.info(f"  Address: {info.parsed_addresses()}")
    log.info(f"  Properties: {info.properties}")

    is_playing = parse_status_flags(info.properties)
    state_str = "PLAYING" if is_playing else "IDLE"

    if not last_state_initialized:
        # Startup: silently record current state, only fire webhook if PLAYING
        # Avoids triggering IDLE automation on every add-on restart
        last_state = state_str
        last_state_initialized = True
        log.info(f"  → Initial state on startup: {state_str}")
        if is_playing:
            log.info("  Device is already playing on startup, firing PLAYING webhook.")
            call_webhook(f"{HA_URL}/api/webhook/{WEBHOOK_PLAYING}")
        else:
            log.info("  Device is idle on startup, not firing any webhook.")
        return

    # Normal operation — only fire on genuine state changes
    if state_str == last_state:
        log.info(f"  State unchanged ({state_str}), skipping webhook.")
        return

    last_state = state_str
    log.info(f"  → State changed to: {state_str}")

    if is_playing:
        call_webhook(f"{HA_URL}/api/webhook/{WEBHOOK_PLAYING}")
    else:
        call_webhook(f"{HA_URL}/api/webhook/{WEBHOOK_IDLE}")


def main():
    log.info("Starting AirPlay Watcher...")
    log.info(f"  HA URL: {HA_URL}")
    log.info(f"  Device IP filter: {DEVICE_IP or 'none (watching all AirPlay devices)'}")
    log.info(f"  Webhook PLAYING: {WEBHOOK_PLAYING}")
    log.info(f"  Webhook IDLE: {WEBHOOK_IDLE}")

    zeroconf = Zeroconf()

    browser_raop = ServiceBrowser(zeroconf, "_raop._tcp.local.", handlers=[on_service_state_change])
    browser_airplay = ServiceBrowser(zeroconf, "_airplay._tcp.local.", handlers=[on_service_state_change])

    log.info("Listening for mDNS updates... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        zeroconf.close()
        log.info("Stopped.")


if __name__ == "__main__":
    main()