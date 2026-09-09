from __future__ import annotations

import uvicorn

from games_intel.api.app import create_app
from games_intel.settings import load_settings


def main() -> None:
    settings = load_settings()
    app = create_app(settings, enable_outbox_relay=True)
    uvicorn.run(
        app,
        host=settings.api.host,
        port=settings.api.port,
        log_level=settings.app.log_level.lower(),
    )


if __name__ == "__main__":
    main()
