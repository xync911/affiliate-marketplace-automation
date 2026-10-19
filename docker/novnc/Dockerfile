# Remote browser for manual account login (Jalur A - browser session).
# Chrome runs with a real display (Xvfb) and is visible via noVNC on port 6080.
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto-cjk \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY docker/novnc/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV DISPLAY=:99
EXPOSE 6080 9222

CMD ["/entrypoint.sh"]
