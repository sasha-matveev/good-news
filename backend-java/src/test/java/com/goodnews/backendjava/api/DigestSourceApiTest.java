package com.goodnews.backendjava.api;

import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
@Testcontainers(disabledWithoutDocker = true)
class DigestSourceApiTest {
    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("good_news")
            .withUsername("good_news")
            .withPassword("good-news-secret");

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("good-news.database.postgres-host", POSTGRESQL::getHost);
        registry.add("good-news.database.postgres-port", POSTGRESQL::getFirstMappedPort);
        registry.add("good-news.database.postgres-database", POSTGRESQL::getDatabaseName);
        registry.add("good-news.database.postgres-user", POSTGRESQL::getUsername);
        registry.add("good-news.database.postgres-password", POSTGRESQL::getPassword);
    }

    @Autowired
    WebTestClient client;

    @Autowired
    DatabaseClient database;

    @BeforeEach
    void clean() {
        database.sql(
                        "TRUNCATE TABLE digest_items, digests, read_later, post_analysis, feedback, technical_events, posts, sources RESTART IDENTITY CASCADE")
                .then()
                .block();
    }

    @Test
    void digestHistoryListsOnlySentProductDigestsAndReturnsOrderedItems() {
        sql("INSERT INTO sources(id,original_url) VALUES (1,'https://source.example')");
        sql(
                "INSERT INTO posts(id,source_id,canonical_url,title,raw_content,content_hash,ingest_metadata) VALUES (1,1,'https://p/1','First','x','h1','{}'),(2,1,'https://p/2','Second','x','h2','{}')");
        sql("INSERT INTO feedback(post_id,state) VALUES (2,'interesting')");
        sql(
                "INSERT INTO digests(id,digest_type,scheduled_for,status,subject,html_body,sent_at) VALUES (1,'daily',NOW(),'sent','Daily','<p>D</p>','2026-04-01T10:00:00Z'),(2,'weekly',NOW(),'sent','Weekly','<p>W</p>','2026-04-02T10:00:00Z'),(3,'daily',NOW(),'pending',NULL,NULL,NULL),(4,'internal',NOW(),'sent',NULL,NULL,NOW())");
        sql("INSERT INTO digest_items(id,digest_id,post_id,rank_position) VALUES (1,2,2,2),(2,2,1,1)");

        client.get()
                .uri("/api/digests")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$[0].id")
                .isEqualTo(2)
                .jsonPath("$[0].included_post_count")
                .isEqualTo(2)
                .jsonPath("$[1].id")
                .isEqualTo(1)
                .jsonPath("$.length()")
                .isEqualTo(2);
        client.get()
                .uri("/api/digests/2")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.sent_at")
                .isEqualTo("2026-04-02T10:00:00Z")
                .jsonPath("$.title")
                .isEqualTo("Weekly")
                .jsonPath("$.included_posts[0].post_id")
                .isEqualTo(1)
                .jsonPath("$.included_posts[1].post_id")
                .isEqualTo(2)
                .jsonPath("$.included_posts[1].feedback_state")
                .isEqualTo("interesting")
                .jsonPath("$.rendered_html")
                .isEqualTo("<p>W</p>");
        client.get()
                .uri("/api/digests/3")
                .exchange()
                .expectStatus()
                .isNotFound()
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Digest not found");
    }

    @Test
    void sourcesSupportListLogCreateUpdateAndErrors() {
        sql(
                "INSERT INTO sources(original_url,display_name,status,active) VALUES ('https://existing.example','Existing','ready',true)");
        sql(
                "INSERT INTO posts(id,source_id,canonical_url,title,raw_content,content_hash,ingest_metadata) VALUES (1,1,'https://p/1','Post','x','h1','{}')");
        client.get()
                .uri("/api/sources")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$[0].post_count")
                .isEqualTo(1)
                .jsonPath("$[0].status")
                .isEqualTo("ready");
        client.get()
                .uri("/api/sources/1/log")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.log.length()")
                .isEqualTo(0)
                .jsonPath("$.done")
                .isEqualTo(true)
                .jsonPath("$.status")
                .isEqualTo("ready");
        client.get()
                .uri("/api/sources/999/log")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.done")
                .isEqualTo(true)
                .jsonPath("$.status")
                .doesNotExist();

        client.post()
                .uri("/api/sources")
                .bodyValue(Map.of("url", " new.example/path/?q=1#fragment "))
                .exchange()
                .expectStatus()
                .isCreated()
                .expectBody()
                .jsonPath("$.original_url")
                .isEqualTo("https://new.example/path")
                .jsonPath("$.status")
                .isEqualTo("pending")
                .jsonPath("$.active")
                .isEqualTo(true)
                .jsonPath("$.post_count")
                .isEqualTo(0);
        client.post()
                .uri("/api/sources")
                .bodyValue(Map.of("url", "https://new.example/path/other?ignored=yes"))
                .exchange()
                .expectStatus()
                .isCreated();
        client.post()
                .uri("/api/sources")
                .bodyValue(Map.of("url", "https://new.example/path/?another=ignored"))
                .exchange()
                .expectStatus()
                .isEqualTo(409)
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Source already exists for https://new.example/path");
        client.post()
                .uri("/api/sources")
                .bodyValue(Map.of("url", "not a url"))
                .exchange()
                .expectStatus()
                .isCreated()
                .expectBody()
                .jsonPath("$.original_url")
                .isEqualTo("https://not a url");

        client.patch()
                .uri("/api/sources/1")
                .bodyValue(Map.of("active", false))
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.active")
                .isEqualTo(false)
                .jsonPath("$.post_count")
                .isEqualTo(1);
        client.patch()
                .uri("/api/sources/999")
                .bodyValue(Map.of("active", false))
                .exchange()
                .expectStatus()
                .isNotFound();
        client.patch()
                .uri("/api/sources/1")
                .bodyValue(Map.of())
                .exchange()
                .expectStatus()
                .isEqualTo(422);
        client.delete().uri("/api/sources/999").exchange().expectStatus().isNotFound();
    }

    @Test
    void deleteSourceRemovesEveryDependentRecord() {
        sql("INSERT INTO sources(id,original_url) VALUES (1,'https://delete.example')");
        sql(
                "INSERT INTO posts(id,source_id,canonical_url,title,raw_content,content_hash,ingest_metadata) VALUES (1,1,'https://p/1','Post','x','h1','{}')");
        sql("INSERT INTO feedback(post_id,state) VALUES (1,'interesting')");
        sql("INSERT INTO post_analysis(post_id) VALUES (1)");
        sql("INSERT INTO read_later(post_id) VALUES (1)");
        sql("INSERT INTO digests(id,digest_type,scheduled_for) VALUES (1,'daily',NOW())");
        sql("INSERT INTO digest_items(digest_id,post_id,rank_position) VALUES (1,1,1)");
        sql("INSERT INTO technical_events(subsystem,event_code,summary,source_id) VALUES ('source','test','event',1)");
        client.delete()
                .uri("/api/sources/1")
                .exchange()
                .expectStatus()
                .isNoContent()
                .expectBody()
                .isEmpty();
        for (String table : new String[] {
            "sources", "posts", "feedback", "post_analysis", "read_later", "digest_items", "technical_events"
        }) {
            Long count = database.sql("SELECT COUNT(*) AS count FROM " + table)
                    .map((row, metadata) -> row.get("count", Long.class))
                    .one()
                    .block();
            org.assertj.core.api.Assertions.assertThat(count).as(table).isZero();
        }
    }

    private void sql(String statement) {
        database.sql(statement).then().block();
    }
}
