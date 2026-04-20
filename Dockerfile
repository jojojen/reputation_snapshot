FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app

# Litestream binary
RUN apt-get update && apt-get install -y --no-install-recommends wget ca-certificates \
    && wget -q https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.deb \
    && dpkg -i litestream-v0.3.13-linux-amd64.deb \
    && rm litestream-v0.3.13-linux-amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Python packages (Playwright already installed in base image)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY . .

# Runtime directories
RUN mkdir -p /data captures/html captures/text captures/screenshots keys

EXPOSE 5000

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
