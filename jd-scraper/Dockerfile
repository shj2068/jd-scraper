# Build stage for Node.js signing service
FROM node:20-slim AS node-builder

WORKDIR /app/node
COPY node/package.json node/package-lock.json* ./
RUN npm install --production && npm cache clean --force

COPY node/ .

# Runtime stage
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JD_RPC_PORT=3001 \
    JD_RPC_POOL_SIZE=3 \
    JD_RPC_HEADLESS=true

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Node.js service from builder
COPY --from=node-builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-builder /app/node /app/node
RUN ln -s /usr/local/lib/node_modules/.bin/* /usr/local/bin/ 2>/dev/null || true

# Copy application code
COPY python/ /app/python/
COPY config/ /app/config/
COPY main.py agent.py agent_report.py pyproject.toml ./

# Create data directories
RUN mkdir -p /app/data/cookies /app/data/reports /app/data/scraped \
             /app/data/categories /app/data/debug /app/data/intercepted \
             /app/data/exports /app/data/screenshots

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3001/health || exit 1

CMD ["sh", "-c", "cd /app/node && node server.js & sleep 3 && cd /app && python main.py status"]
