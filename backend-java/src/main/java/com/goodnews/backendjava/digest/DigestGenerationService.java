package com.goodnews.backendjava.digest;

import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.service.PostService;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.reactive.TransactionalOperator;
import reactor.core.publisher.Mono;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Service
public final class DigestGenerationService {
    private static final int MAX_INCLUDED_POSTS = 5;

    private final PostService posts;
    private final DigestRepository digests;
    private final DigestEmailRenderer renderer;
    private final GoodNewsProperties properties;
    private final ObjectMapper objectMapper;
    private final TransactionalOperator transactions;

    public DigestGenerationService(
            PostService posts,
            DigestRepository digests,
            DigestEmailRenderer renderer,
            GoodNewsProperties properties,
            ObjectMapper objectMapper,
            TransactionalOperator transactions) {
        this.posts = posts;
        this.digests = digests;
        this.renderer = renderer;
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.transactions = transactions;
    }

    public Mono<GeneratedDigest> generateDaily(Instant now) {
        return generate(DigestType.DAILY, now, Duration.ofDays(1));
    }

    public Mono<GeneratedDigest> generateWeekly(Instant now) {
        return generate(DigestType.WEEKLY, now, Duration.ofDays(7));
    }

    private Mono<GeneratedDigest> generate(DigestType type, Instant now, Duration lookback) {
        return Mono.defer(() -> {
                    String frontendOrigin = WebUrlPolicy.requireOrigin(
                            properties.email().publicFrontendOrigin(), "GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN");
                    String contentApiOrigin = WebUrlPolicy.requireOrigin(
                            properties.email().publicContentApiOrigin(), "GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN");
                    String subject = subject(type, now);
                    return posts.listRankedDigestCandidates(now.minus(lookback), now)
                            .flatMap(candidates -> {
                                List<DigestEmailPost> included = candidates.stream()
                                        .limit(MAX_INCLUDED_POSTS)
                                        .map(this::toEmailPost)
                                        .toList();
                                int moreCount = Math.max(0, candidates.size() - included.size());
                                return digests.createGenerated(type, now, subject, metadata(frontendOrigin))
                                        .flatMap(digestId -> {
                                            String htmlBody = renderer.render(
                                                    subject,
                                                    included,
                                                    moreCount,
                                                    contentApiOrigin + "/api/feedback",
                                                    digestId);
                                            GeneratedDigest result = new GeneratedDigest(
                                                    digestId, type, subject, htmlBody, included, moreCount);
                                            return digests.saveRenderedContent(digestId, htmlBody, included)
                                                    .thenReturn(result);
                                        });
                            });
                })
                .as(transactions::transactional);
    }

    private DigestEmailPost toEmailPost(PostService.DigestCandidate post) {
        return new DigestEmailPost(
                post.postId(),
                post.title(),
                post.sourceName(),
                post.canonicalUrl(),
                post.summaryRu(),
                post.verdict(),
                post.verdictReason(),
                post.relevanceScore());
    }

    private String subject(DigestType type, Instant now) {
        String date = now.atZone(ZoneOffset.UTC).toLocalDate().toString();
        return type == DigestType.DAILY ? "Good News digest for " + date : "Good News weekly digest for " + date;
    }

    private String metadata(String frontendOrigin) {
        try {
            return objectMapper.writeValueAsString(Map.of("frontend_base_url", frontendOrigin));
        } catch (JacksonException exception) {
            throw new IllegalStateException("Digest metadata is not serializable", exception);
        }
    }
}
