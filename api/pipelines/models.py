from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    Boolean,
    DateTime,
    UniqueConstraint,
    func,
)

from sqlalchemy.dialects.postgresql import (
    UUID,
    JSONB,
    ENUM,
)

from sqlalchemy.orm import relationship

from api.common.db import (
    Base,
    generate_uuid,
    CreatedAtMixin,
    TimestampMixin,
)

from api.common.enums import PipelineNodeType, RunStatus
from api.common.db_types import run_status_enum

class Pipeline(TimestampMixin, Base):
    __tablename__ = "pipelines"
    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(16), nullable=False)
    deleted_at = Column(DateTime(timezone=True), index=True, nullable=True)

    nodes = relationship("PipelineNode", back_populates="pipeline")
    project = relationship("Project", back_populates="pipelines")
    tests = relationship("TestCase",  back_populates="pipeline")
    runs = relationship("PipelineRuns", back_populates="pipeline")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_pipline_name_user_id",),
    )

class PipelineNode(TimestampMixin, Base):
    __tablename__ = "pipeline_nodes"
    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)
    name = Column(String(16), nullable=False)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    node_type = Column(ENUM(PipelineNodeType), nullable=False)
    config = Column(JSONB(), default=dict, nullable=False)
    deleted_at = Column(DateTime(timezone=True), index=True, nullable=True)

    pipeline = relationship("Pipeline", back_populates="nodes")

class PipelineRuns(TimestampMixin, Base):
    __tablename__ = "pipeline_runs"
    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id"), nullable=False)

    status = Column(
        run_status_enum,
        nullable=False,
        default=RunStatus.PENDING,
        server_default=RunStatus.PENDING.value,
        index=True,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Final text produced by the last node.
    output = Column(Text, nullable=True)
    # Per-node breakdown: [{"node_id", "name", "node_type", "output"/"passed", "error"}].
    node_results = Column(JSONB, nullable=False, default=list, server_default="[]")
    # Populated only when status == ERROR.
    error = Column(Text, nullable=True)

    pipeline = relationship("Pipeline", back_populates="runs")