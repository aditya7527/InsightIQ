from sqlalchemy import Table, Column, Integer, String, MetaData, DateTime, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import registry

mapper_registry = registry()
metadata = MetaData()


datasets = Table(
    "datasets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("path", String, nullable=False),
    Column("schema", JSON),
    Column("rows", Integer),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


reports = Table(
    "reports",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("dataset_id", Integer),
    Column("type", String),
    Column("payload", JSON),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


admin_metrics = Table(
    "admin_metrics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("reports_generated", Integer, default=0),
    Column("avg_latency_ms", Float, default=0.0),
    Column("last_updated", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)


users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String, nullable=False, unique=True),
    Column("hashed_password", String, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
