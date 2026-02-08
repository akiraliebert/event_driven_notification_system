"""Cross-dialect JSON column type.

Uses JSONB on PostgreSQL for indexing and query capabilities,
falls back to plain JSON on other dialects (SQLite in tests).
"""

import sqlalchemy as sa
from sqlalchemy.types import TypeDecorator


class JSONBCompatible(TypeDecorator):
    """A JSON column that renders as JSONB on PostgreSQL, JSON elsewhere."""

    impl = sa.JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: sa.Dialect) -> sa.types.TypeEngine:
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(sa.JSON())
