# camwall in a container, for a home server or a screen left on: see the README's "Docker" section.
# Run it with the host's network (compose.yaml does), so that camwall's page stays on the host's 127.0.0.1:8780 and
# phones on the Wi-Fi pair on port 8781, as when it runs directly.
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 camwall \
    && mkdir /data && chown camwall /data

WORKDIR /app
COPY . .
USER camwall
ENV CAMWALL_DATA=/data XDG_CACHE_HOME=/data/cache PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
VOLUME /data
CMD ["python", "camwall.py", "--no-open"]
