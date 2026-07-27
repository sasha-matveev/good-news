package com.goodnews.backendjava;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.migration.DatabaseMigrationRunner;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.Network;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.startupcheck.OneShotStartupCheckStrategy;
import org.testcontainers.images.builder.ImageFromDockerfile;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers(disabledWithoutDocker = true)
class AlembicToFlywayMigrationIT {

    private static final Network NETWORK = Network.newNetwork();

    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("good_news")
            .withUsername("good_news")
            .withPassword("good-news-secret")
            .withNetwork(NETWORK)
            .withNetworkAliases("postgres");

    @Test
    void upgradesRealAlembicHeadWithExistingDataAndKeepsPythonRollbackMarker() throws SQLException {
        migrateToRealAlembicHead();
        seedRepresentativeData();

        DatabaseMigrationRunner migrationRunner = new DatabaseMigrationRunner(
                POSTGRESQL.getJdbcUrl(), POSTGRESQL.getUsername(), POSTGRESQL.getPassword());
        migrationRunner.migrate();

        try (Connection connection = connection()) {
            assertThat(singleString(connection, "SELECT version_num FROM alembic_version"))
                    .isEqualTo(DatabaseMigrationRunner.ALEMBIC_HEAD);
            assertThat(singleLong(connection, "SELECT COUNT(*) FROM flyway_schema_history"))
                    .isEqualTo(2L);
            assertThat(singleString(
                            connection,
                            "SELECT type || ':' || version FROM flyway_schema_history ORDER BY installed_rank LIMIT 1"))
                    .isEqualTo("BASELINE:4");
            assertThat(singleString(
                            connection, "SELECT display_name FROM sources WHERE original_url='https://example.com'"))
                    .isEqualTo("Representative source");
            assertThat(singleString(connection, "SELECT title FROM posts WHERE content_hash='representative-hash'"))
                    .isEqualTo("Representative post");
            assertThat(singleString(
                            connection, "SELECT delivery_slot_key FROM digests WHERE subject='Representative digest'"))
                    .isEqualTo("daily:2026-07-27");
            assertThat(singleLong(connection, "SELECT COUNT(*) FROM read_later"))
                    .isEqualTo(1L);
        }

        migrationRunner.migrate();

        try (Connection connection = connection()) {
            assertThat(singleLong(connection, "SELECT COUNT(*) FROM flyway_schema_history"))
                    .isEqualTo(2L);
            assertThat(singleLong(connection, "SELECT COUNT(*) FROM posts")).isEqualTo(1L);
        }
    }

    private void migrateToRealAlembicHead() {
        Path backend = Path.of(System.getProperty("maven.multiModuleProjectDirectory"), "..", "backend")
                .toAbsolutePath()
                .normalize();
        ImageFromDockerfile image = new ImageFromDockerfile("good-news-alembic-head-test", false)
                .withFileFromPath("backend", backend)
                .withDockerfileFromBuilder(builder -> builder.from("python:3.14-slim")
                        .workDir("/app")
                        .copy("backend", "/app/backend")
                        .run("pip install --no-cache-dir -e /app/backend")
                        .workDir("/app/backend")
                        .build());

        try (GenericContainer<?> alembic = new GenericContainer<>(image)
                .withNetwork(NETWORK)
                .withEnv(Map.of(
                        "GOOD_NEWS_DATABASE_URL",
                        "postgresql+psycopg://good_news:good-news-secret@postgres:5432/good_news"))
                .withCommand("python", "-m", "alembic", "-c", "alembic.ini", "upgrade", "head")
                .withStartupCheckStrategy(new OneShotStartupCheckStrategy())) {
            alembic.start();
            assertThat(alembic.getCurrentContainerInfo().getState().getExitCodeLong())
                    .as(alembic.getLogs())
                    .isZero();
        }
    }

    private void seedRepresentativeData() throws SQLException {
        try (Connection connection = connection();
                Statement statement = connection.createStatement()) {
            statement.executeUpdate(
                    """
                    INSERT INTO sources(display_name, original_url, status)
                    VALUES ('Representative source', 'https://example.com', 'active')
                    """);
            statement.executeUpdate(
                    """
                    INSERT INTO posts(source_id, canonical_url, title, raw_content, content_hash, ingest_metadata)
                    VALUES (
                        (SELECT id FROM sources WHERE original_url='https://example.com'),
                        'https://example.com/post',
                        'Representative post',
                        'Body',
                        'representative-hash',
                        '{}'
                    )
                    """);
            statement.executeUpdate(
                    """
                    INSERT INTO read_later(post_id)
                    VALUES ((SELECT id FROM posts WHERE content_hash='representative-hash'))
                    """);
            statement.executeUpdate(
                    """
                    INSERT INTO digests(
                        digest_type, scheduled_for, status, subject, delivery_slot_key
                    ) VALUES (
                        'daily', '2026-07-27T08:00:00Z', 'sent',
                        'Representative digest', 'daily:2026-07-27'
                    )
                    """);
        }
    }

    private Connection connection() throws SQLException {
        return DriverManager.getConnection(POSTGRESQL.getJdbcUrl(), POSTGRESQL.getUsername(), POSTGRESQL.getPassword());
    }

    private String singleString(Connection connection, String sql) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql);
                ResultSet resultSet = statement.executeQuery()) {
            assertThat(resultSet.next()).isTrue();
            return resultSet.getString(1);
        }
    }

    private long singleLong(Connection connection, String sql) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql);
                ResultSet resultSet = statement.executeQuery()) {
            assertThat(resultSet.next()).isTrue();
            return resultSet.getLong(1);
        }
    }
}
