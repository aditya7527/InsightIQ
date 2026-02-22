import re
from sqlalchemy import inspect


DATASET_TABLE_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")


def validate_dataset_table_name(table_name: str) -> str:
    if not DATASET_TABLE_PATTERN.fullmatch(table_name or ""):
        raise ValueError(f"Invalid table name format: {table_name}")
    return table_name


def ensure_table_exists(engine, table_name: str) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        raise ValueError("Dataset table not found.")
