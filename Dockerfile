FROM python:3.12-slim

# Install dependencies for wkhtmltopdf
RUN apt-get update && apt-get install -y \
    wget \
    xvfb \
    libfontconfig1 \
    libfreetype6 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libssl3 \
    ca-certificates \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf from GitHub releases (pre-built binary for Debian Bookworm)
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get update && apt-get install -y ./wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && rm wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app/src

# Railway cron: runs agent.py on schedule defined in railway.toml
CMD ["python", "/app/src/agent.py"]
