ALTER TABLE digests ADD COLUMN delivery_slot_key VARCHAR(128);

CREATE UNIQUE INDEX uq_digests_delivery_slot_key
    ON digests (delivery_slot_key)
    WHERE delivery_slot_key IS NOT NULL;
