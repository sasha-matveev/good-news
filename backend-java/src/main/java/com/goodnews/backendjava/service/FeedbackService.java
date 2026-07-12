package com.goodnews.backendjava.service;

import com.goodnews.backendjava.api.dto.FeedbackDtos;
import com.goodnews.backendjava.config.GoodNewsProperties;
import java.net.URI;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.util.UriComponentsBuilder;
import reactor.core.publisher.Mono;

@Service
public class FeedbackService {

    private final PostService postService;
    private final DatabaseClient databaseClient;
    private final GoodNewsProperties properties;

    public FeedbackService(PostService postService, DatabaseClient databaseClient, GoodNewsProperties properties) {
        this.postService = postService;
        this.databaseClient = databaseClient;
        this.properties = properties;
    }

    @Transactional
    public Mono<FeedbackDtos.FeedbackResponse> updateFeedback(long postId, String state) {
        return postService
                .requirePostExists(postId)
                .then(upsertFeedback(postId, state))
                .map(savedState -> new FeedbackDtos.FeedbackResponse(postId, savedState));
    }

    @Transactional
    public Mono<ResponseEntity<Void>> saveFeedback(long postId, String state, String digestId) {
        return postService
                .requirePostExists(postId)
                .then(upsertFeedback(postId, state))
                .flatMap(savedState -> maybeSaveReadLater(postId, savedState).thenReturn(savedState))
                .map(savedState -> ResponseEntity.status(HttpStatus.TEMPORARY_REDIRECT)
                        .location(buildRedirectUri(postId, savedState, digestId))
                        .build());
    }

    Mono<String> currentFeedbackState(long postId) {
        return databaseClient
                .sql("SELECT state FROM feedback WHERE post_id = :postId")
                .bind("postId", postId)
                .map((row, metadata) -> row.get("state", String.class))
                .one();
    }

    Mono<Void> deleteFeedback(long postId) {
        return databaseClient
                .sql("DELETE FROM feedback WHERE post_id = :postId")
                .bind("postId", postId)
                .fetch()
                .rowsUpdated()
                .then();
    }

    private Mono<String> upsertFeedback(long postId, String state) {
        return databaseClient
                .sql(
                        """
                INSERT INTO feedback (post_id, state)
                VALUES (:postId, :state)
                ON CONFLICT (post_id) DO UPDATE
                SET state = EXCLUDED.state,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING state
                """)
                .bind("postId", postId)
                .bind("state", state)
                .map((row, metadata) -> row.get("state", String.class))
                .one();
    }

    private Mono<Void> maybeSaveReadLater(long postId, String state) {
        if (!"want_to_read".equals(state)) {
            return Mono.empty();
        }
        return postService.saveReadLater(postId);
    }

    private URI buildRedirectUri(long postId, String state, String digestId) {
        String origin = publicFrontendOrigin();
        if (digestId != null && !digestId.isBlank()) {
            String path = "want_to_read".equals(state) ? "/want-to-read" : "/digests";
            return UriComponentsBuilder.fromUriString(origin)
                    .path(path)
                    .queryParam("digest_id", digestId)
                    .queryParam("feedback", state)
                    .queryParam("from", "digest_email")
                    .queryParam("post_id", Long.toString(postId))
                    .build(true)
                    .toUri();
        }
        String path = "want_to_read".equals(state) ? "/want-to-read" : "/feed";
        return UriComponentsBuilder.fromUriString(origin).path(path).build(true).toUri();
    }

    private String publicFrontendOrigin() {
        String explicitOrigin = properties.email().publicFrontendOrigin();
        if (explicitOrigin != null && !explicitOrigin.isBlank()) {
            return explicitOrigin.strip().replaceAll("/+$", "");
        }
        throw new IllegalStateException(
                "Missing public origin contract GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN; set it explicitly for user-facing absolute URLs.");
    }
}
