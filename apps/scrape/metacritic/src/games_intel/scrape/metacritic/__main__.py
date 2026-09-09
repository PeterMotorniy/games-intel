from __future__ import annotations

import uvicorn

from games_intel.scrape.metacritic.app import create_app
from games_intel.settings import load_settings


def main() -> None:
    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level=settings.app.log_level.lower())


if __name__ == "__main__":
    main()
