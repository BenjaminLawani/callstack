"""Shared SQLAlchemy column types.

The ``run_status`` Postgres ENUM is referenced by two tables (``pipeline_runs``
and ``test_case_runs``). A Postgres ENUM type can only be created once, so both
columns must share a *single* ENUM instance — otherwise ``create_all`` would try
to ``CREATE TYPE run_status`` twice and fail. Import this instance in both
models rather than constructing ``ENUM(RunStatus)`` inline.
"""

from sqlalchemy.dialects.postgresql import ENUM

from .enums import RunStatus

run_status_enum = ENUM(
    RunStatus,
    name="run_status",
    values_callable=lambda enum: [member.value for member in enum],
)
