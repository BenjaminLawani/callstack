"""Persisted transcription metrics.

Every transcription — whether it ran as a ``voice`` pipeline node or through the
standalone transcription tester — records one ``transcription_metrics`` row. This
is the durable home for latency data (time to first token, total latency, real
time factor) so runs can be compared over time instead of the numbers living only
inside a run's JSON blob.
"""

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
)

from sqlalchemy.dialects.postgresql import (
    UUID,
    JSONB,
)

from api.common.db import (
    Base,
    generate_uuid,
    TimestampMixin,
)


class TranscriptionMetric(TimestampMixin, Base):
    __tablename__ = "transcription_metrics"

    id = Column(UUID(as_uuid=True), default=generate_uuid, primary_key=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Set when the transcription happened inside a pipeline run / voice node.
    # Null for standalone transcription tests.
    pipeline_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    provider = Column(String(32), nullable=False, server_default="assemblyai")
    mode = Column(String(16), nullable=False)          # streaming | batch
    speech_model = Column(String(64), nullable=True)
    audio_url = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)

    # Latency + quality metrics.
    ttft_ms = Column(Integer, nullable=True)           # time to first token
    total_ms = Column(Integer, nullable=True)          # total wall-clock latency
    audio_duration_ms = Column(Integer, nullable=True)
    real_time_factor = Column(Float, nullable=True)
    word_count = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)

    # Assertion verdict, populated when the transcription was checked against a
    # spec (the standalone tester or an inline validation).
    valid = Column(Boolean, nullable=True)
    checks = Column(JSONB, nullable=False, default=list, server_default="[]")

    error = Column(Text, nullable=True)
    raw = Column(JSONB, nullable=False, default=dict, server_default="{}")
