from sqlalchemy import (
    Column,
    String,
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

from api.common.enums import NodeType

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

class PipelineNode(TimestampMixin, Base):
    __tablename__ = "pipeline_nodes"
    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    node_type = Column(ENUM(NodeType), nullable=False)
    deleted_at = Column(DateTime(timezone=True), index=True, nullable=True)

    pipeline = relationship("Pipeline", back_populates="nodes")