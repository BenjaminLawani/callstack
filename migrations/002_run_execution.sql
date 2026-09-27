-- 002: pipeline + test case run execution
--
-- Matches the columns added to:
--   api/pipelines/models.py    -> PipelineRuns
--   api/test_cases/models.py   -> TestCaseRun
-- and the new `run_status` enum in api/common/enums.py.
--
-- init_db() uses Base.metadata.create_all(), which creates the run_status type
-- and any *missing* tables on a fresh database, but never alters existing ones.
-- Run this by hand once against any database that already has the
-- pipeline_runs / test_case_runs tables:
--
--   psql "$DATABASE_URL" -f migrations/002_run_execution.sql

BEGIN;

-- Enum shared by both run tables. CREATE TYPE has no IF NOT EXISTS, so guard it.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'run_status') THEN
        CREATE TYPE run_status AS ENUM ('pending', 'running', 'passed', 'failed', 'error');
    END IF;
END$$;

-- pipeline_runs: status/timing/output. Defaults here match the model's
-- server_default, so they stay in place (unlike migration 001).
ALTER TABLE pipeline_runs
    ADD COLUMN IF NOT EXISTS status       run_status   NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS started_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS finished_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS output       TEXT,
    ADD COLUMN IF NOT EXISTS node_results JSONB        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS error        TEXT;

CREATE INDEX IF NOT EXISTS ix_pipeline_runs_status ON pipeline_runs (status);

-- test_case_runs: link to the pipeline run it evaluated, plus verdict/results.
ALTER TABLE test_case_runs
    ADD COLUMN IF NOT EXISTS pipeline_run_id UUID
        REFERENCES pipeline_runs (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS status       run_status   NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS started_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS finished_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS output       TEXT,
    ADD COLUMN IF NOT EXISTS results      JSONB        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS error        TEXT;

CREATE INDEX IF NOT EXISTS ix_test_case_runs_status ON test_case_runs (status);

COMMIT;
