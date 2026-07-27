ALTER TABLE digests ADD COLUMN IF NOT EXISTS delivery_slot_key VARCHAR(128);

CREATE UNIQUE INDEX IF NOT EXISTS uq_digests_delivery_slot_key
    ON digests (delivery_slot_key)
    WHERE delivery_slot_key IS NOT NULL;

-- Python remains the serving and rollback runtime during coexistence. A clean
-- Flyway install therefore needs the frozen Alembic marker that Python checks
-- at startup. On an Alembic-origin database this table and row already exist.
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

INSERT INTO alembic_version (version_num)
SELECT '20260725_01_digest_slots'
WHERE NOT EXISTS (SELECT 1 FROM alembic_version);
