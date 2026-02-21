import re
from sqlalchemy import inspect


DATASET_TABLE_PATTERN = re.compile(r"^dataset_[a-f0-9]{32}$")


def validate_dataset_table_name(table_name: str) -> str:
    if not DATASET_TABLE_PATTERN.fullmatch(table_name or ""):
        raise ValueError("Invalid table name format.")
    return table_name


def ensure_table_exists(engine, table_name: str) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        raise ValueError("Dataset table not found.")
