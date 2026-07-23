FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install .

RUN chmod +x scripts/start_render.sh \
    && mkdir -p logs outputs data/private \
    && useradd --create-home --shell /bin/bash pliris \
    && chown -R pliris:pliris /app

USER pliris

EXPOSE 10000

CMD ["bash", "scripts/start_render.sh"]
