from sqlalchemy import (
    Column,
    DateTime,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    Integer
)

from sqlalchemy.dialects.postgresql import (
    UUID,
    JSONB,
    ENUM
)

from sqlalchemy.orm import relationship

from api.common.db import (
    Base,
    generate_uuid,
    TimestampMixin,
    CreatedAtMixin,
)

from api.common.enums import RunStatus
from api.common.db_types import run_status_enum
class TestCaseNode(TimestampMixin, Base):
    __tablename__ = "test_case_nodes"

    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    test_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False
    )

    name = Column(String(16), nullable=False)
    description = Column(String(32))
    deleted_at = Column(DateTime(timezone=True))

    should_fail = Column(
        Boolean,
        nullable=False,
        server_default="false"
    )

    assertions = Column(
        JSONB,
        nullable=False,
        default=dict
    )

    position = Column(Integer, nullable=False)

    test_case = relationship(
        "TestCase",
        back_populates="nodes"
    )


class TestCase(TimestampMixin, Base):
    __tablename__ = "test_cases"

    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)

    name = Column(String(32), nullable=False)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    pipeline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False
    )

    deleted_at = Column(DateTime(timezone=True))

    nodes = relationship(
        "TestCaseNode",
        back_populates="test_case",
        order_by="TestCaseNode.position",
        cascade="all, delete-orphan"
    )

    pipeline = relationship(
        "Pipeline",
        back_populates="tests"
    )

    runs = relationship(
        "TestCaseRun",
        back_populates="test_case"
    )


class TestCaseRun(TimestampMixin, Base):
    __tablename__ = "test_case_runs"

    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)

    test_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False
    )

    # The pipeline execution this test case evaluated against.
    pipeline_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(
        run_status_enum,
        nullable=False,
        default=RunStatus.PENDING,
        server_default=RunStatus.PENDING.value,
        index=True,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # The pipeline output the assertions ran against.
    output = Column(Text, nullable=True)
    # Per-test-node results:
    # [{"node_id", "name", "should_fail", "passed", "checks": [...]}].
    results = Column(JSONB, nullable=False, default=list, server_default="[]")
    error = Column(Text, nullable=True)

    test_case = relationship(
        "TestCase",
        back_populates="runs"
    )