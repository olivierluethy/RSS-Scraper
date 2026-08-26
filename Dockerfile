FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY rss_watcher ./rss_watcher
COPY config.example.yaml ./

# Persist the seen-store on a volume so de-dup survives container restarts.
ENV RSS_WATCHER_CONFIG=/app/config.yaml
VOLUME ["/data"]

# Runs the watcher; provide config.yaml via a bind mount or env vars.
ENTRYPOINT ["python", "-m", "rss_watcher"]
CMD ["--config", "/app/config.yaml"]
