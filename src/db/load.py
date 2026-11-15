"""Load cleaned tables into SQLite and/or PostgreSQL."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from src.paths import POSTGRES_URL, SQLITE_PATH, SQLITE_URL, SRC

SCHEMA_PATH = SRC / "db" / "schema.sql"


def get_engine(kind: str = "sqlite"):
    if kind == "sqlite":
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(SQLITE_URL)
    if kind == "postgres":
        return create_engine(POSTGRES_URL)
    raise ValueError(f"Unknown engine kind: {kind}")


def init_schema(kind: str = "sqlite") -> None:
    engine = get_engine(kind)
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # SQLite needs AUTOINCREMENT tweak; strip PG-only comments is fine as-is
    with engine.begin() as conn:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))


def write_table(
    df: pd.DataFrame,
    name: str,
    kind: str = "sqlite",
    if_exists: str = "replace",
) -> int:
    if df is None or df.empty:
        return 0
    engine = get_engine(kind)
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d")
    out.to_sql(name, engine, if_exists=if_exists, index=False, method="multi", chunksize=1000)
    return len(out)


def run_sql(sql: str, kind: str = "sqlite", params: dict | None = None) -> pd.DataFrame:
    engine = get_engine(kind)
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})
