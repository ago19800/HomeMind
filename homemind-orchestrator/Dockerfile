FROM python:3.12-slim

LABEL \
    io.hass.name="HomeMind Orchestrator" \
    io.hass.description="Autonomous AI Agent for Home Assistant" \
    io.hass.type="addon"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl jq findutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Increment CACHEBUST to force pip reinstall on rebuild
ARG CACHEBUST=146
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY spazzatura_calendario_2026.json ./
COPY person_config.default.json ./
COPY run.sh /
RUN chmod +x /run.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8099/health || exit 1

CMD ["/run.sh"]
