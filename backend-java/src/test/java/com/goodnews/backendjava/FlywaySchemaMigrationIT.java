package com.goodnews.backendjava;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.config.ReactiveDatabaseSmokeProbe;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationVersion;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import reactor.test.StepVerifier;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@Testcontainers(disabledWithoutDocker = true)
class FlywaySchemaMigrationIT {

    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("good_news")
            .withUsername("good_news")
            .withPassword("good-news-secret");

    private static final Map<String, TableSpec> EXPECTED_TABLES = expectedTables();

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("good-news.database.postgres-host", POSTGRESQL::getHost);
        registry.add("good-news.database.postgres-port", POSTGRESQL::getFirstMappedPort);
        registry.add("good-news.database.postgres-database", POSTGRESQL::getDatabaseName);
        registry.add("good-news.database.postgres-user", POSTGRESQL::getUsername);
        registry.add("good-news.database.postgres-password", POSTGRESQL::getPassword);
    }

    @Autowired
    private ReactiveDatabaseSmokeProbe smokeProbe;

    @Test
    void flywayMigratesEmptyDatabaseAndCreatesExpectedSchema() throws SQLException {
        StepVerifier.create(smokeProbe.verifyConnectivity())
                .assertNext(canConnect -> assertThat(canConnect).isTrue())
                .verifyComplete();

        try (Connection connection = DriverManager.getConnection(
                POSTGRESQL.getJdbcUrl(), POSTGRESQL.getUsername(), POSTGRESQL.getPassword())) {
            assertFlywayHistory(connection);
            assertTables(connection);
            assertDigestDeliverySlotIndex(connection);
        }
    }

    @Test
    void migrationFivePreservesLegacyDuplicateDigestSlots() throws SQLException {
        String schema = "legacy_digest_upgrade";
        Flyway.configure()
                .dataSource(POSTGRESQL.getJdbcUrl(), POSTGRESQL.getUsername(), POSTGRESQL.getPassword())
                .schemas(schema)
                .defaultSchema(schema)
                .target(MigrationVersion.fromVersion("4"))
                .load()
                .migrate();

        try (Connection connection = DriverManager.getConnection(
                        POSTGRESQL.getJdbcUrl(), POSTGRESQL.getUsername(), POSTGRESQL.getPassword());
                Statement statement = connection.createStatement()) {
            connection.setSchema(schema);
            statement.executeUpdate(
                    "INSERT INTO digests(digest_type,scheduled_for,status) VALUES ('daily','2026-07-17T12:00:00Z','sent'),('daily','2026-07-17T12:00:00Z','failed')");
        }

        Flyway.configure()
                .dataSource(POSTGRESQL.getJdbcUrl(), POSTGRESQL.getUsername(), POSTGRESQL.getPassword())
                .schemas(schema)
                .defaultSchema(schema)
                .load()
                .migrate();

        try (Connection connection = DriverManager.getConnection(
                        POSTGRESQL.getJdbcUrl(), POSTGRESQL.getUsername(), POSTGRESQL.getPassword());
                PreparedStatement statement = connection.prepareStatement(
                        "SELECT COUNT(*) FROM " + schema + ".digests WHERE delivery_slot_key IS NULL")) {
            try (ResultSet resultSet = statement.executeQuery()) {
                assertThat(resultSet.next()).isTrue();
                assertThat(resultSet.getLong(1)).isEqualTo(2L);
            }
        }
    }

    private void assertFlywayHistory(Connection connection) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT version, success FROM flyway_schema_history ORDER BY installed_rank")) {
            try (ResultSet resultSet = statement.executeQuery()) {
                Map<String, Boolean> migrations = new LinkedHashMap<>();
                while (resultSet.next()) {
                    migrations.put(resultSet.getString("version"), resultSet.getBoolean("success"));
                }

                assertThat(migrations)
                        .containsExactly(
                                Map.entry("1", true),
                                Map.entry("2", true),
                                Map.entry("3", true),
                                Map.entry("4", true),
                                Map.entry("5", true));
            }
        }
    }

    private void assertTables(Connection connection) throws SQLException {
        assertThat(fetchTableNames(connection)).containsAll(EXPECTED_TABLES.keySet());

        for (Map.Entry<String, TableSpec> entry : EXPECTED_TABLES.entrySet()) {
            assertColumns(connection, entry.getKey(), entry.getValue().columns());
            assertUniqueConstraints(connection, entry.getKey(), entry.getValue().uniqueConstraints());
            assertForeignKeys(connection, entry.getKey(), entry.getValue().foreignKeys());
        }
    }

    private void assertDigestDeliverySlotIndex(Connection connection) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT indexdef FROM pg_indexes WHERE schemaname=current_schema() AND tablename='digests' AND indexname='uq_digests_delivery_slot_key'")) {
            try (ResultSet resultSet = statement.executeQuery()) {
                assertThat(resultSet.next()).isTrue();
                assertThat(resultSet.getString("indexdef"))
                        .contains("UNIQUE INDEX", "delivery_slot_key", "WHERE (delivery_slot_key IS NOT NULL)");
            }
        }
    }

    private Set<String> fetchTableNames(Connection connection) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """)) {
            try (ResultSet resultSet = statement.executeQuery()) {
                Set<String> tableNames = new java.util.LinkedHashSet<>();
                while (resultSet.next()) {
                    tableNames.add(resultSet.getString("table_name"));
                }
                return tableNames;
            }
        }
    }

    private void assertColumns(Connection connection, String tableName, Map<String, ColumnSpec> expectedColumns)
            throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                """
            SELECT column_name, data_type, is_nullable, column_default, is_identity
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            """)) {
            statement.setString(1, tableName);

            try (ResultSet resultSet = statement.executeQuery()) {
                Map<String, ColumnSnapshot> actualColumns = new LinkedHashMap<>();
                while (resultSet.next()) {
                    actualColumns.put(
                            resultSet.getString("column_name"),
                            new ColumnSnapshot(
                                    resultSet.getString("data_type"),
                                    "YES".equals(resultSet.getString("is_nullable")),
                                    resultSet.getString("column_default"),
                                    "YES".equals(resultSet.getString("is_identity"))));
                }

                assertThat(actualColumns.keySet()).containsExactlyInAnyOrderElementsOf(expectedColumns.keySet());
                expectedColumns.forEach((columnName, spec) -> {
                    ColumnSnapshot actual = actualColumns.get(columnName);
                    assertThat(actual.dataType()).isEqualTo(spec.dataType());
                    assertThat(actual.nullable()).isEqualTo(spec.nullable());
                    assertThat(actual.identity()).isEqualTo(spec.identity());
                    if (spec.defaultFragment() == null) {
                        assertThat(actual.columnDefault()).isNull();
                    } else {
                        assertThat(actual.columnDefault()).contains(spec.defaultFragment());
                    }
                });
            }
        }
    }

    private void assertUniqueConstraints(Connection connection, String tableName, Set<String> expectedConstraints)
            throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_schema = 'public' AND table_name = ? AND constraint_type = 'UNIQUE'
            """)) {
            statement.setString(1, tableName);

            try (ResultSet resultSet = statement.executeQuery()) {
                Set<String> actualConstraints = new java.util.LinkedHashSet<>();
                while (resultSet.next()) {
                    actualConstraints.add(resultSet.getString("constraint_name"));
                }

                assertThat(actualConstraints).containsExactlyInAnyOrderElementsOf(expectedConstraints);
            }
        }
    }

    private void assertForeignKeys(Connection connection, String tableName, Set<ForeignKeySpec> expectedForeignKeys)
            throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                """
            SELECT tc.constraint_name, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.table_schema = 'public' AND tc.table_name = ? AND tc.constraint_type = 'FOREIGN KEY'
            """)) {
            statement.setString(1, tableName);

            try (ResultSet resultSet = statement.executeQuery()) {
                Set<ForeignKeySpec> actualForeignKeys = new java.util.LinkedHashSet<>();
                while (resultSet.next()) {
                    actualForeignKeys.add(new ForeignKeySpec(
                            resultSet.getString("constraint_name"),
                            resultSet.getString("column_name"),
                            resultSet.getString("foreign_table_name"),
                            resultSet.getString("foreign_column_name")));
                }

                assertThat(actualForeignKeys).containsExactlyInAnyOrderElementsOf(expectedForeignKeys);
            }
        }
    }

    private static Map<String, TableSpec> expectedTables() {
        Map<String, TableSpec> tables = new LinkedHashMap<>();

        tables.put(
                "sources",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("display_name", nullableColumn("character varying")),
                                Map.entry("original_url", requiredColumn("character varying")),
                                Map.entry("feed_url", nullableColumn("character varying")),
                                Map.entry("strategy_kind", nullableColumn("character varying")),
                                Map.entry("strategy_config", nullableColumn("text")),
                                Map.entry("active", new ColumnSpec("boolean", false, "true", false)),
                                Map.entry("status", new ColumnSpec("character varying", false, "'pending'", false)),
                                Map.entry("last_success_at", nullableColumn("timestamp with time zone")),
                                Map.entry("last_failure_at", nullableColumn("timestamp with time zone")),
                                Map.entry("needs_readaptation", new ColumnSpec("boolean", false, "false", false)),
                                Map.entry("readaptation_reason", nullableColumn("text")),
                                Map.entry(
                                        "created_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false)),
                                Map.entry(
                                        "updated_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false)),
                                Map.entry("consecutive_failures", new ColumnSpec("integer", false, "0", false))),
                        Set.of("uq_sources_original_url"),
                        Set.of()));

        tables.put(
                "settings",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("key", requiredColumn("character varying")),
                                Map.entry("value", nullableColumn("text")),
                                Map.entry(
                                        "created_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false)),
                                Map.entry(
                                        "updated_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of("uq_settings_key"),
                        Set.of()));

        tables.put(
                "secret_settings",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("key", requiredColumn("character varying")),
                                Map.entry("encrypted_value", requiredColumn("text")),
                                Map.entry(
                                        "updated_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of("uq_secret_settings_key"),
                        Set.of()));

        tables.put(
                "technical_events",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("severity", new ColumnSpec("character varying", false, "'info'", false)),
                                Map.entry("subsystem", requiredColumn("character varying")),
                                Map.entry("event_code", requiredColumn("character varying")),
                                Map.entry("summary", requiredColumn("text")),
                                Map.entry("details", nullableColumn("text")),
                                Map.entry("source_id", nullableColumn("integer")),
                                Map.entry(
                                        "created_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of(),
                        Set.of(new ForeignKeySpec("fk_technical_events_source_id", "source_id", "sources", "id"))));

        tables.put(
                "posts",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("source_id", requiredColumn("integer")),
                                Map.entry("canonical_url", requiredColumn("character varying")),
                                Map.entry("title", requiredColumn("character varying")),
                                Map.entry("published_at", nullableColumn("timestamp with time zone")),
                                Map.entry("raw_content", requiredColumn("text")),
                                Map.entry("content_hash", requiredColumn("character varying")),
                                Map.entry("ingest_metadata", requiredColumn("text")),
                                Map.entry(
                                        "created_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false)),
                                Map.entry(
                                        "updated_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of("uq_posts_canonical_url", "uq_posts_content_hash"),
                        Set.of(new ForeignKeySpec("fk_posts_source_id", "source_id", "sources", "id"))));

        tables.put(
                "feedback",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("post_id", requiredColumn("integer")),
                                Map.entry("state", requiredColumn("character varying")),
                                Map.entry(
                                        "created_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false)),
                                Map.entry(
                                        "updated_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of("uq_feedback_post_id"),
                        Set.of(new ForeignKeySpec("fk_feedback_post_id", "post_id", "posts", "id"))));

        tables.put(
                "post_analysis",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("post_id", requiredColumn("integer")),
                                Map.entry("summary_ru", nullableColumn("text")),
                                Map.entry("metadata_json", nullableColumn("text")),
                                Map.entry(
                                        "created_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false)),
                                Map.entry(
                                        "updated_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of("uq_post_analysis_post_id"),
                        Set.of(new ForeignKeySpec("fk_post_analysis_post_id", "post_id", "posts", "id"))));

        tables.put(
                "preference_profile",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("summary", nullableColumn("text")),
                                Map.entry("metadata_json", nullableColumn("text")),
                                Map.entry(
                                        "updated_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of(),
                        Set.of()));

        tables.put(
                "digests",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("digest_type", requiredColumn("character varying")),
                                Map.entry("scheduled_for", requiredColumn("timestamp with time zone")),
                                Map.entry("status", new ColumnSpec("character varying", false, "'pending'", false)),
                                Map.entry("recipient_email", nullableColumn("character varying")),
                                Map.entry("subject", nullableColumn("character varying")),
                                Map.entry("html_body", nullableColumn("text")),
                                Map.entry("metadata_json", nullableColumn("text")),
                                Map.entry("delivery_slot_key", nullableColumn("character varying")),
                                Map.entry("sent_at", nullableColumn("timestamp with time zone")),
                                Map.entry(
                                        "created_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of(),
                        Set.of()));

        tables.put(
                "digest_items",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("digest_id", requiredColumn("integer")),
                                Map.entry("post_id", requiredColumn("integer")),
                                Map.entry("rank_position", requiredColumn("integer"))),
                        Set.of(),
                        Set.of(
                                new ForeignKeySpec("fk_digest_items_digest_id", "digest_id", "digests", "id"),
                                new ForeignKeySpec("fk_digest_items_post_id", "post_id", "posts", "id"))));

        tables.put(
                "read_later",
                new TableSpec(
                        Map.ofEntries(
                                Map.entry("id", identityColumn("integer")),
                                Map.entry("post_id", requiredColumn("integer")),
                                Map.entry(
                                        "created_at",
                                        new ColumnSpec("timestamp with time zone", false, "CURRENT_TIMESTAMP", false))),
                        Set.of("uq_read_later_post_id"),
                        Set.of(new ForeignKeySpec("fk_read_later_post_id", "post_id", "posts", "id"))));

        return tables;
    }

    private static ColumnSpec identityColumn(String dataType) {
        return new ColumnSpec(dataType, false, null, true);
    }

    private static ColumnSpec requiredColumn(String dataType) {
        return new ColumnSpec(dataType, false, null, false);
    }

    private static ColumnSpec nullableColumn(String dataType) {
        return new ColumnSpec(dataType, true, null, false);
    }

    private record TableSpec(
            Map<String, ColumnSpec> columns, Set<String> uniqueConstraints, Set<ForeignKeySpec> foreignKeys) {}

    private record ColumnSpec(String dataType, boolean nullable, String defaultFragment, boolean identity) {}

    private record ColumnSnapshot(String dataType, boolean nullable, String columnDefault, boolean identity) {}

    private record ForeignKeySpec(
            String constraintName, String columnName, String foreignTableName, String foreignColumnName) {}
}
