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

class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(64), nullable=False)
    slug = Column(String(128), nullable=False, unique=True)
    avatar_url = Column(String(), nullable=True)
    deleted_at = Column(DateTime(timezone=True), index=True, nullable=True)

    pipelines = relationship("Pipeline", back_populates="project")

    __table_args = (
        UniqueConstraint("uq_user_proj_name", "user_id", "name"),
        )