#!/bin/bash
set -e

export DISPLAY=:99

# Virtual framebuffer (Chrome needs a display)
Xvfb :99 -screen 0 1280x900x24 -nolisten tcp &
sleep 1

# VNC server + noVNC web client (port 6080)
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -quiet &
websockify --web /usr/share/novnc 6080 localhost:5900 &

sleep 1

# Persistent Chrome with remote debugging for Playwright CDP connection
exec chromium \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  --disable-blink-features=AutomationControlled \
  --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port=9222 \
  --user-data-dir=/data/profile \
  --window-size=1200,800 \
  --no-first-run \
  --no-default-browser-check \
  about:blank
