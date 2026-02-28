# AirPlay Watcher - Home Assistant Add-on

Monitors your AirPlay device via mDNS and fires HA webhooks when playback starts or stops.

---

## Installation

### Option A — Add this repository (recommended)

1. Go to **Settings → Add-ons → Add-on Store**
2. Click the **3-dot menu** (top right) → **Add repository**
3. Enter: `https://github.com/vaibhavn29/ha-airplay-watcher`
4. Click **Add** → **Close**
5. Refresh the Add-on Store (3-dot menu → **Check for updates** if needed)
6. Find **AirPlay Watcher** under the new repo and click **Install**

### Option B — Local install (copy to your Pi)

Copy the `airplay-watcher` folder to your HA addons directory:

```
/usr/share/hassio/addons/local/airplay-watcher/
```

Via SSH/SCP:
```bash
scp -r airplay-watcher/ root@<your-pi-ip>:/usr/share/hassio/addons/local/
```

Then in HA:

1. Go to **Settings → Add-ons → Add-on Store**
2. Click the 3-dot menu (top right) → **Check for updates**
3. Scroll down to **Local add-ons** — you should see **AirPlay Watcher**
4. Click it → **Install**

### Step 3 — Configure the add-on

In the add-on **Configuration** tab, set (example for device **airplay_device**):

```yaml
ha_url: "http://homeassistant.local:8123"
device_ip: ""
webhook_playing: "airplay_playing"
webhook_idle: "airplay_idle"
```

Use your Home Assistant URL and your AirPlay device's IP (set `device_ip` to its LAN IP so the add-on only reacts to mDNS from that device).

### Step 4 — Binary sensor: Detected / Not Detected

Add to `configuration.yaml` so you get a sensor that shows **Detected** when the device is playing and **Not Detected** when idle:

```yaml
input_boolean:
  airplay_device_detected:
    name: "airplay_device"
    icon: mdi:cast-audio

template:
  - sensor:
      - name: "airplay_device Status"
        unique_id: airplay_device_status
        state: >
          {% if is_state('input_boolean.airplay_device_detected', 'on') %}
            Detected
          {% else %}
            Not Detected
          {% endif %}
        icon: >
          {% if is_state('input_boolean.airplay_device_detected', 'on') %}
            mdi:speaker-play
          {% else %}
            mdi:speaker-off
          {% endif %}
```

The entity `sensor.airplay_device_status` will show **Detected** or **Not Detected** in the UI.

### Step 5 — Automations for the binary sensor

Create two automations so the webhooks update the sensor.

**Automation 1 — Playing → Detected**
- **Trigger:** Webhook, Webhook ID: `airplay_playing`
- **Action:** Turn on `input_boolean.airplay_device_detected`

**Automation 2 — Idle → Not Detected**
- **Trigger:** Webhook, Webhook ID: `airplay_idle`
- **Action:** Turn off `input_boolean.airplay_device_detected`

You can add more actions (e.g. turn on amplifier when playing, turn off when idle).

### Step 6 — Start the add-on

Go back to the add-on page and click **Start**. Check the **Log** tab to confirm it's listening.

---

## How It Works

Your AirPlay device (e.g. airplay_device) advertises itself on the LAN via mDNS as `_raop._tcp` (AirPlay audio).

When something starts streaming to it, the device updates its mDNS TXT record with a status flag (`sf`):
- `sf=0` → idle → **Not Detected**
- `sf=4` (or non-zero) → active stream → **Detected**

The add-on listens for those mDNS updates and calls your HA webhooks so you can drive a binary sensor and automations.

---

## Troubleshooting

- The add-on uses **host networking** (set in config.yaml) so it can see mDNS on your LAN.
- Check the add-on **Log** tab for “Service update” and state changes when you start or stop playback.
- If the device has a changing IP, give it a static IP or a DHCP reservation on your router.
- Ensure `ha_url` is reachable from the host (e.g. `http://homeassistant.local:8123`).
