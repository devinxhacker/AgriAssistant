"""CLI script to seed the glossary and verified knowledge base into SQLite."""

from app.config import get_settings
from app.db.database import Database
from app.main import seed_initial_data
from app.pipeline.orchestrator import AgriPipeline


def main() -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    pipeline = AgriPipeline(settings, db)
    seed_initial_data(db, pipeline)
    with db.connection() as conn:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        terms = conn.execute("SELECT COUNT(*) FROM glossary_terms").fetchone()[0]
    print(f"Seeded {docs} documents ({chunks} chunks) and {terms} glossary terms.")


if __name__ == "__main__":
    main()
