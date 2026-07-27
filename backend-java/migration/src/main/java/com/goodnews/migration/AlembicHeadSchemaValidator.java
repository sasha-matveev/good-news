package com.goodnews.migration;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import org.flywaydb.core.Flyway;

final class AlembicHeadSchemaValidator {

    private final String url;
    private final String user;
    private final String password;

    AlembicHeadSchemaValidator(String url, String user, String password) {
        this.url = url;
        this.user = user;
        this.password = password;
    }

    void validate(Connection connection) throws SQLException {
        this.assertAlembicRevision(connection);
        String expectedSchema =
                "flyway_expected_" + UUID.randomUUID().toString().replace("-", "");
        this.createSchema(connection, expectedSchema);
        try {
            Flyway.configure()
                    .dataSource(this.url, this.user, this.password)
                    .schemas(expectedSchema)
                    .defaultSchema(expectedSchema)
                    .locations("classpath:db/migration")
                    .target(DatabaseMigrationRunner.ALEMBIC_SCHEMA_VERSION)
                    .load()
                    .migrate();
            this.assertEqual(
                    "tables",
                    this.tableSnapshot(connection, connection.getSchema()),
                    this.tableSnapshot(connection, expectedSchema));
            this.assertEqual(
                    "columns",
                    this.columnSnapshot(connection, connection.getSchema()),
                    this.columnSnapshot(connection, expectedSchema));
            this.assertEqual(
                    "constraints",
                    this.constraintSnapshot(connection, connection.getSchema()),
                    this.constraintSnapshot(connection, expectedSchema));
            this.assertEqual(
                    "indexes",
                    this.indexSnapshot(connection, connection.getSchema()),
                    this.indexSnapshot(connection, expectedSchema));
        } finally {
            this.dropSchema(connection, expectedSchema);
        }
    }

    private void assertAlembicRevision(Connection connection) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("SELECT version_num FROM alembic_version");
                ResultSet resultSet = statement.executeQuery()) {
            if (!resultSet.next() || !DatabaseMigrationRunner.ALEMBIC_HEAD.equals(resultSet.getString(1))) {
                throw new IllegalStateException(
                        "Refusing Flyway baseline: expected Alembic revision " + DatabaseMigrationRunner.ALEMBIC_HEAD);
            }
            if (resultSet.next()) {
                throw new IllegalStateException("Refusing Flyway baseline: alembic_version contains multiple rows");
            }
        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "Refusing Flyway baseline: alembic_version is missing or unreadable", exception);
        }
    }

    private Set<String> tableSnapshot(Connection connection, String schema) throws SQLException {
        return this.snapshot(
                connection,
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = ?
                  AND table_type = 'BASE TABLE'
                  AND table_name NOT IN ('alembic_version', 'flyway_schema_history')
                ORDER BY table_name
                """,
                schema);
    }

    private Set<String> columnSnapshot(Connection connection, String schema) throws SQLException {
        return this.snapshot(
                connection,
                """
                SELECT table_name || '.' || column_name || ':' ||
                       data_type || COALESCE('(' || character_maximum_length || ')', '') || ':' ||
                       is_nullable || ':' ||
                       CASE
                           WHEN is_identity = 'YES' OR column_default LIKE 'nextval(%' THEN '<generated>'
                           ELSE COALESCE(column_default, '')
                       END
                FROM information_schema.columns
                WHERE table_schema = ?
                  AND table_name NOT IN ('alembic_version', 'flyway_schema_history')
                ORDER BY table_name, ordinal_position
                """,
                schema);
    }

    private Set<String> constraintSnapshot(Connection connection, String schema) throws SQLException {
        return this.snapshot(
                connection,
                """
                SELECT c.relname || '.' || con.conname || ':' || pg_get_constraintdef(con.oid)
                FROM pg_constraint con
                JOIN pg_class c ON c.oid = con.conrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = ?
                  AND c.relname NOT IN ('alembic_version', 'flyway_schema_history')
                ORDER BY c.relname, con.conname
                """,
                schema);
    }

    private Set<String> indexSnapshot(Connection connection, String schema) throws SQLException {
        return this.snapshot(
                connection,
                """
                SELECT t.relname || '.' || i.relname || ':' || pg_get_indexdef(ix.indexrelid)
                FROM pg_index ix
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = ?
                  AND t.relname NOT IN ('alembic_version', 'flyway_schema_history')
                ORDER BY t.relname, i.relname
                """,
                schema);
    }

    private Set<String> snapshot(Connection connection, String sql, String schema) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, schema);
            try (ResultSet resultSet = statement.executeQuery()) {
                Set<String> snapshot = new LinkedHashSet<>();
                while (resultSet.next()) {
                    snapshot.add(this.normalize(resultSet.getString(1), schema));
                }
                return snapshot;
            }
        }
    }

    private String normalize(String value, String schema) {
        return value.toLowerCase(Locale.ROOT)
                .replace('"' + schema.toLowerCase(Locale.ROOT) + "\".", "")
                .replace(schema.toLowerCase(Locale.ROOT) + ".", "")
                .replace("::character varying", "")
                .replaceAll("\\s+", " ")
                .trim();
    }

    private void assertEqual(String objectType, Set<String> actual, Set<String> expected) {
        if (!actual.equals(expected)) {
            Set<String> missing = new LinkedHashSet<>(expected);
            missing.removeAll(actual);
            Set<String> unexpected = new LinkedHashSet<>(actual);
            unexpected.removeAll(expected);
            throw new IllegalStateException("Refusing Flyway baseline: Alembic-head "
                    + objectType
                    + " mismatch; missing="
                    + missing
                    + ", unexpected="
                    + unexpected);
        }
    }

    private void createSchema(Connection connection, String schema) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute("CREATE SCHEMA " + schema);
        }
    }

    private void dropSchema(Connection connection, String schema) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute("DROP SCHEMA " + schema + " CASCADE");
        }
    }
}
