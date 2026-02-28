#!/usr/bin/with-contenv bashio

export HA_URL=$(bashio::config 'ha_url')
export DEVICE_IP=$(bashio::config 'device_ip')
export WEBHOOK_PLAYING=$(bashio::config 'webhook_playing')
export WEBHOOK_IDLE=$(bashio::config 'webhook_idle')

bashio::log.info "Starting AirPlay Watcher..."
exec python3 /app/airplay_watcher.py
