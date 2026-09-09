from __future__ import annotations

import asyncio
import logging

from games_intel.workers.reviews.runtime import build_runtime


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    runtime = build_runtime()
    stop = asyncio.Event()
    asyncio.run(runtime.run(stop))


if __name__ == "__main__":
    main()
