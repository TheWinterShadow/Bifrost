# syntax=docker/dockerfile:1

# ── Stage 1: build wheel ──────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir hatch

COPY pyproject.toml ./
COPY bifrost/ ./bifrost/

RUN hatch build -t wheel


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim

# HAP-python needs avahi/mDNS on Linux for service discovery.
# Installing avahi-daemon covers both the daemon and the dbus dependency.
RUN apt-get update \
    && apt-get install -y --no-install-recommends avahi-daemon dbus \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/dist/*.whl /tmp/

RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Persist HAP state (pairing info, etc.) in a named volume.
VOLUME ["/data"]
ENV BIFROST_STATE_FILE=/data/bifrost.state
# Required at runtime: pass via -e GOVEE_API_KEY=<your-key> or Docker secrets.
ENV GOVEE_API_KEY=""

EXPOSE 51826/tcp
EXPOSE 51826/udp

# avahi needs dbus at runtime
CMD ["sh", "-c", "mkdir -p /var/run/dbus && dbus-daemon --system --fork && avahi-daemon --daemonize --no-chroot && bifrost"]
