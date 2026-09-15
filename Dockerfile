# ── LLM-as-a-Judge Reliability Lab — Production Dockerfile ────────────────────
# Deploys the FastAPI backend with co-located data files required by read-only
# research endpoints. Scientific content is served from PostgreSQL + CSV
# artifacts; no experiments are executed at build or runtime.
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

WORKDIR /app

# Install PostgreSQL client libs for psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ backend/

# Copy read-only data files required by research endpoints
COPY qualitative_data/ qualitative_data/
COPY data/canonical/ data/canonical/

# PORT is set by Render at runtime (default 10000)
ENV PORT=10000

EXPOSE ${PORT}

# --proxy-headers: trust X-Forwarded-For from Render's reverse proxy
# --forwarded-allow-ips='*': safe because Render is the only ingress
CMD uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --proxy-headers \
    --forwarded-allow-ips='*'
