#!/usr/bin/env python3
"""Migrate data from the legacy SQLite database to Postgres."""
import os
from pathlib import Path as _Path
from sqlalchemy import create_engine
from app.database import Base

SQLITE_PATH = os.getenv("SQLITE_PATH", "data/email_system.db")
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/email_system",
)

def main():
    if not _Path(SQLITE_PATH).exists():
        raise SystemExit(f"SQLite database not found at {SQLITE_PATH}")

    sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
    pg_engine = create_engine(POSTGRES_URL)

    # Recreate schema fresh
    Base.metadata.drop_all(pg_engine)
    Base.metadata.create_all(pg_engine)

    with sqlite_engine.connect() as sqlite_conn, pg_engine.begin() as pg_conn:
        for table in Base.metadata.sorted_tables:
            rows = sqlite_conn.execute(table.select()).fetchall()
            if not rows:
                continue
            data = [dict(row._mapping) for row in rows]
            pg_conn.execute(table.insert(), data)
            print(f"Copied {len(data)} rows into {table.name}")

    print("Migration complete.")


if __name__ == "__main__":
    main()
