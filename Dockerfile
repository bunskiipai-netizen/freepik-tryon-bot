FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build deps for Pillow
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libjpeg62-turbo libfreetype6 zlib1g \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY freepik_tryon_bot ./freepik_tryon_bot
RUN pip install -e .

VOLUME ["/app/data"]
CMD ["python", "-m", "freepik_tryon_bot"]
