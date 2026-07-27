ALTER TABLE digests ADD COLUMN IF NOT EXISTS delivery_slot_key VARCHAR(128);

CREATE UNIQUE INDEX IF NOT EXISTS uq_digests_delivery_slot_key
    ON digests (delivery_slot_key)
    WHERE delivery_slot_key IS NOT NULL;
