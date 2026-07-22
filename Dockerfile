FROM python:3.13-slim

LABEL org.opencontainers.image.title="TIL90 Field Desk"
LABEL org.opencontainers.image.description="Local USB monitoring and browser console for a Loadsensing TIL90"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --requirement requirements.txt

COPY analysis/protocol/ ./analysis/protocol/
COPY tools/ ./tools/
COPY web/ ./web/
RUN mkdir -p /app/data

EXPOSE 8765

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=4 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=2).read()"]

CMD ["python", "-m", "tools.web_service", "--host", "0.0.0.0", "--port", "8765", "--database", "/app/data/til90.sqlite3", "--auto-monitor", "--measurement-interval", "10", "--health-interval", "60"]

