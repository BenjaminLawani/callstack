from sqlalchemy import (
    Column,
    DateTime,
    String,
    Integer,
    func,
    ForeignKey,
    UniqueConstraint
)

from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID,
    ENUM,
)

from sqlalchemy.orm import relationship

from api.common.db import (
    Base,
    CreatedAtMixin,
    generate_uuid,
    TimestampMixin,
)

from api.common.enums import LoginMethod

class User(CreatedAtMixin, Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), 
                default=generate_uuid, 
                primary_key=True)
    
    email = Column(String(128), 
                   nullable=False, 
                   unique=True, 
                   index=True)

    password = Column(String(),
                      nullable=True,
                      )

    login_method = Column(ENUM(LoginMethod), nullable=False)
    
    deleted_at = Column(DateTime(timezone=True), 
                        nullable=True, 
                        index=True)

    profile = relationship("UserProfile", uselist=False, back_populates="user")

class UserProfile(TimestampMixin, Base):
    __tablename__ = "profiles"
    id = Column(UUID(as_uuid=True), 
                   default=generate_uuid, 
                   primary_key=True)

    user_id = Column(UUID(as_uuid=True),
                     ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False)

    username = Column(String(64), unique=True, index=True, nullable=False)

    preferences = Column(JSONB(), default=dict, nullable=False)

    avatar_url = Column(String(), nullable=True)

    user = relationship("User", back_populates="profile")