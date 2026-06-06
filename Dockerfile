# Outcome Readiness Agents — single image running all 3 processes
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5050 \
    HOST=0.0.0.0 \
    SCAN_AGENT_PORT=8088 \
    INTAKE_AGENT_PORT=8087 \
    DB_PATH=/data/runs.db

WORKDIR /app

# System deps (minimal — pypdf/python-docx are pure-python)
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

RUN chmod +x start.container.sh \
 && mkdir -p /data

EXPOSE 5050 8087 8088

CMD ["./start.container.sh"]
