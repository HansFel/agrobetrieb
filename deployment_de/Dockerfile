FROM python:3.13-slim

# Build-Argument für Git-Commit-Hash
ARG COMMIT_HASH=unknown
ENV COMMIT_HASH=${COMMIT_HASH}

WORKDIR /app

# Installiere System-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Kopiere Anforderungen
COPY requirements.txt .

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn==21.2.0 flask-migrate==4.0.5

# Kopiere App
COPY . .

# Wenn kein COMMIT_HASH übergeben, aus .git lesen und in Datei schreiben
RUN if [ "$COMMIT_HASH" = "unknown" ] && [ -d ".git" ]; then \
      COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown"); \
    fi && echo "$COMMIT_HASH" > /app/BUILD_HASH

# Entrypoint-Script (Migrationen VOR Gunicorn)
COPY deployment_de/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose Port
EXPOSE 5000

# Health Check (start-period lang genug fuer Migrations)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Entrypoint fuehrt Migrationen aus, dann startet Gunicorn
ENTRYPOINT ["/entrypoint.sh"]
