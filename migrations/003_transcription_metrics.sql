-- 003: transcription metrics
--
-- Matches api/metrics/models.py -> TranscriptionMetric.
--
-- init_db() uses Base.metadata.create_all(), which creates this table on a fresh
-- database, but never alters an existing schema. Run this by hand once against a
-- database that predates the metrics table:
--
--   psql "$DATABASE_URL" -f migrations/003_transcription_metrics.sql

BEGIN;

CREATE TABLE IF NOT EXISTS transcription_metrics (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    pipeline_run_id   UUID REFERENCES pipeline_runs (id) ON DELETE CASCADE,
    node_id           UUID REFERENCES pipeline_nodes (id) ON DELETE SET NULL,

    provider          VARCHAR(32)  NOT NULL DEFAULT 'assemblyai',
    mode              VARCHAR(16)  NOT NULL,
    speech_model      VARCHAR(64),
    audio_url         TEXT,
    transcript        TEXT,

    ttft_ms           INTEGER,
    total_ms          INTEGER,
    audio_duration_ms INTEGER,
    real_time_factor  DOUBLE PRECISION,
    word_count        INTEGER,
    confidence        DOUBLE PRECISION,

    valid             BOOLEAN,
    checks            JSONB NOT NULL DEFAULT '[]'::jsonb,

    error             TEXT,
    raw               JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_transcription_metrics_user_id
    ON transcription_metrics (user_id);
CREATE INDEX IF NOT EXISTS ix_transcription_metrics_pipeline_run_id
    ON transcription_metrics (pipeline_run_id);

COMMIT;
