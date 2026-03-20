FROM python:3.12-slim

# Install wkhtmltopdf
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Wrapper so wkhtmltopdf works headless
RUN echo '#!/bin/bash\nxvfb-run -a --server-args="-screen 0, 1024x768x24" /usr/bin/wkhtmltopdf --load-error-handling ignore "$@"' \
    > /usr/local/bin/wkhtmltopdf-headless && chmod +x /usr/local/bin/wkhtmltopdf-headless

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Railway cron: runs agent.py on schedule defined in railway.toml
CMD ["python", "src/agent.py"]
