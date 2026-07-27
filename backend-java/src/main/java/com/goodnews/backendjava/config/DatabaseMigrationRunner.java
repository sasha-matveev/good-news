package com.goodnews.backendjava.config;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationVersion;

public final class DatabaseMigrationRunner {

    public static final long MIGRATION_LOCK_ID = 2042801L;
    public static final String ALEMBIC_HEAD = "20260725_01_digest_slots";
    static final MigrationVersion BASELINE_VERSION = MigrationVersion.fromVersion("4");
    static final MigrationVersion ALEMBIC_SCHEMA_VERSION = MigrationVersion.fromVersion("5");

    private final String url;
    private final String user;
    private final String password;

    public DatabaseMigrationRunner(String url, String user, String password) {
        this.url = url;
        this.user = user;
        this.password = password;
    }

    public void migrate() {
        try (Connection lockConnection = DriverManager.getConnection(this.url, this.user, this.password)) {
            this.lock(lockConnection);
            try {
                Flyway flyway = this.flyway();
                if (this.hasFlywayHistory(lockConnection)) {
                    flyway.migrate();
                } else if (this.isEmptyDatabase(lockConnection)) {
                    flyway.migrate();
                } else {
                    new AlembicHeadSchemaValidator(this.url, this.user, this.password).validate(lockConnection);
                    flyway.baseline();
                    flyway.migrate();
                }
            } finally {
                this.unlock(lockConnection);
            }
        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "Flyway migration failed while holding the database migration lock", exception);
        }
    }

    private Flyway flyway() {
        return Flyway.configure()
                .dataSource(this.url, this.user, this.password)
                .locations("classpath:db/migration")
                .baselineVersion(BASELINE_VERSION)
                .baselineDescription("Alembic head " + ALEMBIC_HEAD)
                .load();
    }

    private boolean hasFlywayHistory(Connection connection) throws SQLException {
        return this.queryBoolean(
                connection, "SELECT to_regclass(current_schema() || '.flyway_schema_history') IS NOT NULL");
    }

    private boolean isEmptyDatabase(Connection connection) throws SQLException {
        return !this.queryBoolean(
                connection,
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_type = 'BASE TABLE'
                )
                """);
    }

    private boolean queryBoolean(Connection connection, String sql) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql);
                ResultSet resultSet = statement.executeQuery()) {
            return resultSet.next() && resultSet.getBoolean(1);
        }
    }

    private void lock(Connection connection) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("SELECT pg_advisory_lock(?)")) {
            statement.setLong(1, MIGRATION_LOCK_ID);
            statement.execute();
        }
    }

    private void unlock(Connection connection) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("SELECT pg_advisory_unlock(?)")) {
            statement.setLong(1, MIGRATION_LOCK_ID);
            statement.execute();
        }
    }
}
