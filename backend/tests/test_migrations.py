"""Postgres-only proof that Alembic migrations reproduce the models exactly.

Runs ``alembic upgrade head`` against a scratch database (``TEST_DATABASE_URL``,
name ending in ``_test``) from an empty schema and compares the result with
``Base.metadata`` in both directions. A model change without a matching
migration (or a migration that adds something the models do not describe) fails
here instead of silently surviving until production.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import UniqueConstraint, create_engine, inspect, text

from app.db import Base
from tests.conftest import BACKEND_ROOT, TEST_DATABASE_URL, alembic_config

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Postgres-only: set TEST_DATABASE_URL to a dedicated database ending in _test",
)

MIGRATIONS = Path(BACKEND_ROOT) / "migrations"


def unique_column_sets(inspector, name: str) -> set[frozenset[str]]:
    """Unique constraints as reported by Postgres, whether backed by a constraint or index."""
    constraints = {
        frozenset(entry["column_names"]) for entry in inspector.get_unique_constraints(name)
    }
    indexes = {
        frozenset(entry["column_names"]) for entry in inspector.get_indexes(name) if entry["unique"]
    }
    return constraints | indexes


def modelled_unique_column_sets(table) -> set[frozenset[str]]:
    modelled = {
        frozenset(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    modelled |= {
        frozenset(column.name for column in index.columns)
        for index in table.indexes
        if index.unique
    }
    modelled |= {frozenset([column.name]) for column in table.columns if column.unique}
    return modelled


def schema_problems(engine) -> list[str]:
    """Every difference between the migrated schema and ``Base.metadata``, both directions."""
    inspector = inspect(engine)
    metadata = Base.metadata
    problems: list[str] = []
    migrated_tables = set(inspector.get_table_names()) - {"alembic_version"}
    modelled_tables = set(metadata.tables)
    for name in sorted(modelled_tables - migrated_tables):
        problems.append(f"model table {name} is missing from the migrated schema")
    for name in sorted(migrated_tables - modelled_tables):
        problems.append(f"migrated schema has table {name} that no model declares")
    for name in sorted(modelled_tables & migrated_tables):
        table = metadata.tables[name]
        migrated_columns = {column["name"] for column in inspector.get_columns(name)}
        modelled_columns = {column.name for column in table.columns}
        for column in sorted(modelled_columns - migrated_columns):
            problems.append(f"model column {name}.{column} is missing from the migrated schema")
        for column in sorted(migrated_columns - modelled_columns):
            problems.append(f"migrated schema has column {name}.{column} that no model declares")
        migrated_indexes = {
            index["name"] for index in inspector.get_indexes(name) if not index["unique"]
        }
        modelled_indexes = {index.name for index in table.indexes if not index.unique}
        for index in sorted(modelled_indexes - migrated_indexes):
            problems.append(f"model index {index} on {name} is missing from the migrated schema")
        for index in sorted(migrated_indexes - modelled_indexes):
            problems.append(f"migrated schema has index {index} on {name} that no model declares")
        migrated_unique = unique_column_sets(inspector, name)
        modelled_unique = modelled_unique_column_sets(table)
        for columns in sorted(modelled_unique - migrated_unique, key=sorted):
            problems.append(f"model unique constraint on {name}{tuple(sorted(columns))} is missing")
        for columns in sorted(migrated_unique - modelled_unique, key=sorted):
            problems.append(
                f"migrated schema has unique constraint on {name}{tuple(sorted(columns))} "
                "that no model declares"
            )
    return problems


def test_upgrade_from_empty_database_matches_head_and_models():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))  # fixed identifier, no user input

        command.upgrade(alembic_config(), "head")

        heads = set(ScriptDirectory(str(MIGRATIONS)).get_heads())
        assert len(heads) == 1, f"expected exactly one migration head, found {sorted(heads)}"
        with engine.connect() as connection:
            installed = set(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
            )
        assert installed == heads, f"alembic_version {installed} does not match head {heads}"

        problems = schema_problems(engine)
        assert not problems, "model/migration drift:\n" + "\n".join(problems)
    finally:
        engine.dispose()
