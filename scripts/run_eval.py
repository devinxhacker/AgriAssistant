"""CLI script to run the automated evaluation suite and print JSON metrics."""

import asyncio
import json

from app.config import get_settings
from app.db.database import Database
from app.eval.runner import run_evaluation
from app.main import seed_initial_data
from app.pipeline.orchestrator import AgriPipeline


async def main() -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    pipeline = AgriPipeline(settings, db)
    seed_initial_data(db, pipeline)
    summary = await run_evaluation(pipeline)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
