from sqlalchemy import (
    Column,
    DateTime,
    String,
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
class TestCaseNode(TimestampMixin, Base):
    __tablename__ = "test_case_nodes"
    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id"), )    
    name = Column(String(16), nullable=False)
    description = Column(String(32), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    should_fail = Column(Boolean(), default=False)
    assertions = Column(JSONB(), default=dict, nullable=False)
    position = Column(Integer(), nullable=False)

    test_case = relationship("TestCase", back_populates="nodes")


class TestCase(TimestampMixin, Base):
    __tablename__ = "test_cases"
    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)
    name = Column(String(32), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id" ,ondelete="CASCADE"), nullable=False)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    nodes = relationship("TestCaseNode", back_populates="test_case", order_by="TestCaseNode.position")
    pipeline = relationship("Pipeline", back_populates="tests")