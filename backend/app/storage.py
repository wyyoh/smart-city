from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, Session, SQLModel, create_engine

from .settings import DATABASE_PATH


def now() -> str:
    return datetime.now(UTC).isoformat()


class Dataset(SQLModel, table=True):
    id: str = Field(primary_key=True)
    filename: str
    sha256: str = Field(index=True)
    imported_at: str = Field(default_factory=now)
    importer_version: str = '1.0.0'
    revision: int = 0
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class SourceRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    dataset_id: str = Field(foreign_key='dataset.id', index=True)
    sheet: str = Field(index=True)
    row: int
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Recipe(SQLModel, table=True):
    id: str = Field(primary_key=True)
    dataset_id: str = Field(foreign_key='dataset.id', index=True)
    source: str = Field(index=True)
    gradation: str
    product: str
    oil_stone_ratio_pct: float | None = None
    rap_nominal_pct: float | None = None
    parent_id: str | None = Field(default=None, index=True)
    kind: str = 'historical'
    created_at: str = Field(default_factory=now)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Measurement(SQLModel, table=True):
    id: str = Field(primary_key=True)
    dataset_id: str = Field(foreign_key='dataset.id', index=True)
    recipe_id: str = Field(foreign_key='recipe.id', index=True)
    metric: str = Field(index=True)
    value: float | None = None
    unit: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Recommendation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    created_at: str = Field(default_factory=now)
    dataset_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Observation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    recipe_id: str = Field(foreign_key='recipe.id', index=True)
    idempotency_key: str = Field(unique=True, index=True)
    created_at: str = Field(default_factory=now)
    state: str = 'draft'
    metric: str
    value: float
    unit: str
    data_scope: str = 'demo'
    use_for_recommendation: bool = False
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


def make_engine(path: Path = DATABASE_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f'sqlite:///{path.as_posix()}', connect_args={'check_same_thread': False})


def initialize(engine):
    SQLModel.metadata.create_all(engine)


engine = make_engine()


def get_session():
    with Session(engine) as session:
        yield session

