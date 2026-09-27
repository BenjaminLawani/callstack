-- 001: add `name` and `config` to pipeline_nodes
--
-- Matches the columns added to api/pipelines/models.py:
--     name   = Column(String(16), nullable=False)
--     config = Column(JSONB(), default=dict, nullable=False)
--
-- init_db() uses Base.metadata.create_all(), which creates missing *tables* but
-- never alters existing ones, so this ALTER has to be run by hand once against
-- any database that already has the pipeline_nodes table.
--
-- Both columns are NOT NULL, so we add them with a temporary DEFAULT to backfill
-- existing rows, then drop the DEFAULT so the schema matches the model (which
-- supplies these values from the application layer).
--
-- Run:  psql "$DATABASE_URL" -f migrations/001_pipeline_nodes_name_config.sql

BEGIN;

ALTER TABLE pipeline_nodes
    ADD COLUMN IF NOT EXISTS name   VARCHAR(16) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS config JSONB       NOT NULL DEFAULT '{}'::jsonb;

-- Give pre-existing rows a readable name (their node type) instead of ''.
UPDATE pipeline_nodes
SET name = LEFT(node_type::text, 16)
WHERE name = '';

-- The model has no server_default for these; keep the DB in sync with it.
ALTER TABLE pipeline_nodes
    ALTER COLUMN name   DROP DEFAULT,
    ALTER COLUMN config DROP DEFAULT;

COMMIT;
