FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

WORKDIR /app

COPY packages/settings /app/packages/settings
COPY packages/contracts /app/packages/contracts
COPY packages/db /app/packages/db
COPY packages/adapters/metacritic /app/packages/adapters/metacritic
COPY apps/scrape/metacritic /app/apps/scrape/metacritic
COPY config.example.yaml /app/config.example.yaml

RUN pip install --no-cache-dir \
    /app/packages/settings \
    /app/packages/contracts \
    /app/packages/db \
    /app/packages/adapters/metacritic \
    /app/apps/scrape/metacritic

ENV APP_CONFIG_PATH=/app/config.example.yaml
EXPOSE 8080

CMD ["python", "-m", "games_intel.scrape.metacritic"]
