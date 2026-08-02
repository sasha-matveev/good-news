DELETE FROM digest_items
WHERE digest_id IN (
    SELECT id FROM digests WHERE digest_type = 'observability_daily'
);

DELETE FROM digests
WHERE digest_type = 'observability_daily';

DELETE FROM settings
WHERE key = 'last_observability_report_sent_at';
