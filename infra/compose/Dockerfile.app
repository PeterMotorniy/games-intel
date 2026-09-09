FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:$PATH" \
    APP_CONFIG_PATH=/app/config.example.yaml \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock /app/
COPY packages /app/packages
COPY apps/api /app/apps/api
COPY apps/workers /app/apps/workers
COPY apps/scrape /app/apps/scrape
COPY config.example.yaml /app/config.example.yaml

ARG PACKAGE=games-intel-api
ARG EXPECT_LANGCHAIN=0
ARG INSTALL_FFMPEG=0

RUN if [ "$INSTALL_FFMPEG" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends ffmpeg \
      && rm -rf /var/lib/apt/lists/*; \
    fi \
    && uv sync --frozen --no-dev --package ${PACKAGE} \
    && if [ "$EXPECT_LANGCHAIN" = "0" ]; then \
         /app/.venv/bin/python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('langchain') is None else 1)"; \
       else \
         /app/.venv/bin/python -c "import langchain"; \
       fi
