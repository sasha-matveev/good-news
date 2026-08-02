TRUNCATE TABLE
    digest_items,
    digests,
    read_later,
    post_analysis,
    feedback,
    posts,
    secret_settings,
    settings,
    sources
RESTART IDENTITY CASCADE;

INSERT INTO sources (
    id, display_name, original_url, feed_url, strategy_kind, strategy_config,
    active, status, consecutive_failures, created_at, updated_at
) VALUES
    (1, 'Alpha', 'https://sources.contract.test/alpha', 'https://sources.contract.test/alpha/feed',
     'feed', '{}', TRUE, 'ready', 0, '2026-04-26T10:00:00Z', '2026-04-26T10:00:00Z'),
    (2, 'Beta', 'https://sources.contract.test/beta', 'https://sources.contract.test/beta/feed',
     'feed', '{}', TRUE, 'ready', 0, '2026-04-26T10:00:00Z', '2026-04-26T10:00:00Z');

INSERT INTO posts (
    id, source_id, canonical_url, title, published_at, raw_content,
    content_hash, ingest_metadata, created_at, updated_at
) VALUES
    (1, 1, 'https://sources.contract.test/alpha/one', 'Alpha One',
     '2026-04-25T09:00:00Z', 'Deterministic alpha content.', 'alpha-one',
     '{"strategy":"feed","published_at_source":"feed"}', '2026-04-26T10:00:00Z', '2026-04-26T10:00:00Z'),
    (2, 2, 'https://sources.contract.test/beta/two', 'Beta Two',
     '2026-04-24T09:00:00Z', 'Deterministic beta content.', 'beta-two',
     '{"strategy":"feed","published_at_source":"feed"}', '2026-04-26T10:00:00Z', '2026-04-26T10:00:00Z');

INSERT INTO post_analysis (
    id, post_id, summary_ru, metadata_json, created_at, updated_at
) VALUES
    (1, 1, 'Альфа', '{"topics":["platform"],"format":"article","technical_depth":"medium","verdict":"interesting","verdict_reason":"Useful.","relevance_score":8}',
     '2026-04-26T10:00:00Z', '2026-04-26T10:00:00Z');

INSERT INTO digests (
    id, digest_type, scheduled_for, status, recipient_email, subject,
    html_body, metadata_json, sent_at, created_at
) VALUES
    (1, 'daily', '2026-04-26T08:00:00Z', 'sent', 'reader@contract.test',
     'Daily digest', '<p>Digest</p>', '{}', '2026-04-26T08:01:00Z',
     '2026-04-26T08:00:00Z');

INSERT INTO digest_items (id, digest_id, post_id, rank_position)
VALUES (1, 1, 1, 1);

SELECT setval(pg_get_serial_sequence('sources', 'id'), 2, true);
SELECT setval(pg_get_serial_sequence('posts', 'id'), 2, true);
SELECT setval(pg_get_serial_sequence('post_analysis', 'id'), 1, true);
SELECT setval(pg_get_serial_sequence('digests', 'id'), 1, true);
SELECT setval(pg_get_serial_sequence('digest_items', 'id'), 1, true);
