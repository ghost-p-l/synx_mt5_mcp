# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

RUN pip install uv==0.5.17

WORKDIR /app

FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

FROM base AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsecret-1-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY src/ /app/src/
COPY config/ /app/config/
COPY mql5/ /app/mql5/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"

EXPOSE 8765 8766

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8765/health', timeout=5)"

ENTRYPOINT ["synx-mt5"]
CMD ["start", "--transport", "stdio"]
