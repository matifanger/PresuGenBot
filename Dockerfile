FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libglib2.0-0 \
    fontconfig \
    fonts-dejavu-core \
    wget \
    ca-certificates \
    curl \
    unzip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Deno JS runtime (required by yt-dlp for YouTube n-challenge solving)
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && deno --version

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
