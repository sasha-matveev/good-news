package com.goodnews.backendjava.service;

import com.goodnews.backendjava.api.contract.ApiHttpException;
import com.goodnews.backendjava.api.dto.PostDtos;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Service
public class PostService {

    private static final Map<String, Double> FEEDBACK_WEIGHTS = Map.of(
            "interesting", 4.0,
            "want_to_read", 5.0,
            "not_interesting", -4.0);
    private static final Map<String, Double> DEPTH_WEIGHTS = Map.of(
            "shallow", 0.1,
            "medium", 0.35,
            "deep", 0.7);

    private final DatabaseClient databaseClient;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public PostService(DatabaseClient databaseClient, ObjectMapper objectMapper, Clock clock) {
        this.databaseClient = databaseClient;
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    public Mono<List<PostDtos.PostResponse>> listPosts(
            Long sourceId,
            String feedbackState,
            String window,
            String sort,
            Integer limit,
            int offset,
            Boolean readLater) {
        OffsetDateTime minPublishedAt = "all".equals(window)
                ? null
                : OffsetDateTime.ofInstant(clock.instant().minus(30, ChronoUnit.DAYS), ZoneOffset.UTC);
        FeedQuery query = new FeedQuery(sourceId, feedbackState, readLater, minPublishedAt, null);
        return fetchPosts(query).collectList().map(rows -> toResponses(rows, !"date".equals(sort), limit, offset));
    }

    public Mono<List<DigestCandidate>> listRankedDigestCandidates(Instant publishedSince, Instant publishedThrough) {
        FeedQuery query = new FeedQuery(
                null,
                null,
                null,
                OffsetDateTime.ofInstant(publishedSince, ZoneOffset.UTC),
                OffsetDateTime.ofInstant(publishedThrough, ZoneOffset.UTC));
        return fetchPosts(query).collectList().map(rows -> toResponses(rows, true, null, 0).stream()
                .map(post -> new DigestCandidate(
                        post.id(),
                        post.title(),
                        post.source_name(),
                        post.canonical_url(),
                        post.summary_ru(),
                        post.verdict(),
                        post.verdict_reason(),
                        post.relevance_score()))
                .toList());
    }

    @Transactional
    public Mono<PostDtos.ReadLaterResponse> updateReadLater(long postId, boolean saved) {
        return requirePostExists(postId)
                .then(saved ? saveReadLater(postId) : clearReadLater(postId))
                .thenReturn(new PostDtos.ReadLaterResponse(postId, saved));
    }

    public Mono<PostDtos.OpenResponse> trackOpen(long postId) {
        return requirePostExists(postId).thenReturn(new PostDtos.OpenResponse(true));
    }

    Mono<Void> requirePostExists(long postId) {
        return databaseClient
                .sql("SELECT id FROM posts WHERE id = :postId")
                .bind("postId", postId)
                .map((row, metadata) -> row.get("id"))
                .first()
                .switchIfEmpty(Mono.error(new ApiHttpException(HttpStatus.NOT_FOUND, "Post not found")))
                .then();
    }

    Mono<Void> saveReadLater(long postId) {
        return databaseClient
                .sql(
                        """
                INSERT INTO read_later (post_id)
                VALUES (:postId)
                ON CONFLICT (post_id) DO NOTHING
                """)
                .bind("postId", postId)
                .fetch()
                .rowsUpdated()
                .then();
    }

    Mono<Void> clearReadLater(long postId) {
        return databaseClient
                .sql("DELETE FROM read_later WHERE post_id = :postId")
                .bind("postId", postId)
                .fetch()
                .rowsUpdated()
                .then();
    }

    private Flux<PostRow> fetchPosts(FeedQuery query) {
        StringBuilder sql = new StringBuilder(
                """
            SELECT
                p.id,
                p.source_id,
                s.display_name AS source_name,
                p.canonical_url,
                p.title,
                p.published_at,
                p.raw_content,
                f.state AS feedback_state,
                (rl.id IS NOT NULL) AS read_later,
                pa.summary_ru,
                pa.metadata_json AS analysis_metadata_json
            FROM posts p
            JOIN sources s ON s.id = p.source_id
            LEFT JOIN feedback f ON f.post_id = p.id
            LEFT JOIN read_later rl ON rl.post_id = p.id
            LEFT JOIN post_analysis pa ON pa.post_id = p.id
            WHERE 1 = 1
            """);
        Map<String, Object> bindings = new HashMap<>();

        if (query.minPublishedAt() != null) {
            sql.append(" AND p.published_at >= :minPublishedAt");
            bindings.put("minPublishedAt", query.minPublishedAt());
        }
        if (query.maxPublishedAt() != null) {
            sql.append(" AND p.published_at < :maxPublishedAt");
            bindings.put("maxPublishedAt", query.maxPublishedAt());
        }
        if (query.sourceId() != null) {
            sql.append(" AND p.source_id = :sourceId");
            bindings.put("sourceId", query.sourceId());
        }
        if ("none".equals(query.feedbackState())) {
            sql.append(" AND f.state IS NULL");
        } else if (query.feedbackState() != null) {
            sql.append(" AND f.state = :feedbackState");
            bindings.put("feedbackState", query.feedbackState());
        }
        if (Boolean.TRUE.equals(query.readLater())) {
            sql.append(" AND rl.id IS NOT NULL");
        } else if (Boolean.FALSE.equals(query.readLater())) {
            sql.append(" AND rl.id IS NULL");
        }

        sql.append(" ORDER BY p.published_at DESC, p.id DESC");

        DatabaseClient.GenericExecuteSpec spec = databaseClient.sql(sql.toString());
        for (Map.Entry<String, Object> binding : bindings.entrySet()) {
            spec = spec.bind(binding.getKey(), binding.getValue());
        }

        return spec.map((row, metadata) -> new PostRow(
                        numberToLong(row.get("id")),
                        numberToLong(row.get("source_id")),
                        row.get("source_name", String.class),
                        row.get("canonical_url", String.class),
                        row.get("title", String.class),
                        offsetDateTime(row.get("published_at")),
                        row.get("raw_content", String.class),
                        row.get("feedback_state", String.class),
                        booleanValue(row.get("read_later")),
                        row.get("summary_ru", String.class),
                        row.get("analysis_metadata_json", String.class)))
                .all();
    }

    private List<PostDtos.PostResponse> toResponses(
            List<PostRow> rows, boolean rankResults, Integer limit, int offset) {
        Map<Long, ParsedAnalysis> analysisByPostId = new HashMap<>();
        List<RankablePost> projections = new ArrayList<>();
        for (PostRow row : rows) {
            ParsedAnalysis analysis = parseAnalysis(row.analysisMetadataJson(), row.summaryRu());
            analysisByPostId.put(row.id(), analysis);
            projections.add(new RankablePost(
                    row.id(),
                    row.title(),
                    row.sourceName(),
                    row.canonicalUrl(),
                    row.publishedAt(),
                    row.rawContent(),
                    row.feedbackState(),
                    analysis));
        }

        Map<Long, RankingResult> rankingByPostId = rankResults ? rankPosts(projections) : Map.of();
        List<PostRow> orderedRows = new ArrayList<>(rows);
        if (rankResults) {
            orderedRows.sort((left, right) -> compareMatchOrder(left, right, analysisByPostId, rankingByPostId));
        }

        int fromIndex = Math.min(offset, orderedRows.size());
        int toIndex = limit == null ? orderedRows.size() : Math.min(fromIndex + limit, orderedRows.size());
        List<PostRow> pagedRows = orderedRows.subList(fromIndex, toIndex);

        List<PostDtos.PostResponse> responses = new ArrayList<>(pagedRows.size());
        for (PostRow row : pagedRows) {
            ParsedAnalysis analysis = analysisByPostId.get(row.id());
            RankingResult ranking = rankingByPostId.get(row.id());
            responses.add(new PostDtos.PostResponse(
                    row.id(),
                    row.sourceId(),
                    row.sourceName(),
                    row.canonicalUrl(),
                    row.title(),
                    formatInstant(row.publishedAt()),
                    null,
                    row.rawContent(),
                    row.feedbackState(),
                    row.readLater(),
                    analysis.summaryRu(),
                    emptyToNull(analysis.verdict()),
                    emptyToNull(analysis.verdictReason()),
                    analysis.relevanceScore(),
                    ranking == null ? null : ranking.explanation()));
        }
        return responses;
    }

    private int compareMatchOrder(
            PostRow left,
            PostRow right,
            Map<Long, ParsedAnalysis> analysisByPostId,
            Map<Long, RankingResult> rankingByPostId) {
        Comparator<PostRow> comparator = Comparator.comparing(
                        (PostRow row) -> analysisByPostId.get(row.id()).relevanceScore() != null ? 1 : 0)
                .thenComparing(row -> analysisByPostId.get(row.id()).relevanceScore() != null
                        ? analysisByPostId.get(row.id()).relevanceScore()
                        : 0)
                .thenComparingDouble(row -> rankingByPostId.get(row.id()).score())
                .thenComparingLong(PostRow::id);

        return comparator.reversed().compare(left, right);
    }

    private Map<Long, RankingResult> rankPosts(List<RankablePost> posts) {
        Map<String, Double> sourceAffinity = new HashMap<>();
        Map<String, Double> topicAffinity = new HashMap<>();
        Map<String, Double> formatAffinity = new HashMap<>();
        List<RankInput> inputs = new ArrayList<>();

        for (RankablePost post : posts) {
            if ("interesting".equals(post.feedbackState()) || "want_to_read".equals(post.feedbackState())) {
                sourceAffinity.merge(nullToEmpty(post.sourceName()), 0.4, Double::sum);
                for (String topic : post.analysis().topics()) {
                    topicAffinity.merge(topic, 0.3, Double::sum);
                }
                if (post.analysis().format() != null) {
                    formatAffinity.merge(post.analysis().format(), 0.2, Double::sum);
                }
            }
            inputs.add(new RankInput(
                    post.postId(),
                    post.sourceName(),
                    post.publishedAt() == null ? 0L : post.publishedAt().toEpochSecond(),
                    post.feedbackState(),
                    post.analysis().topics(),
                    post.analysis().format(),
                    "interesting".equals(post.analysis().verdict()) ? 0.6 : 0.1,
                    DEPTH_WEIGHTS.getOrDefault(nullToEmpty(post.analysis().technicalDepth()), 0.0)));
        }

        long latestEpoch =
                inputs.stream().mapToLong(RankInput::publishedEpoch).max().orElse(0L);
        Map<Long, RankingResult> results = new HashMap<>();
        for (RankInput input : inputs) {
            double feedbackScore = feedbackWeight(input.feedbackState());
            double sourceScore = sourceAffinity.getOrDefault(nullToEmpty(input.sourceName()), 0.0);
            double topicScore = input.topics().stream()
                    .mapToDouble(topic -> topicAffinity.getOrDefault(topic, 0.0))
                    .max()
                    .orElse(0.0);
            double formatScore = formatAffinity.getOrDefault(nullToEmpty(input.format()), 0.0);
            double recencyScore =
                    latestEpoch == 0L ? 0.0 : Math.max(0.0, (((double) input.publishedEpoch()) / latestEpoch) * 0.3);
            double total = feedbackScore
                    + sourceScore
                    + topicScore
                    + formatScore
                    + input.practicalEngineeringScore()
                    + input.technicalDepthScore()
                    + recencyScore;
            String explanation = "feedback=" + (input.feedbackState() == null ? "none" : input.feedbackState())
                    + "; source_affinity=" + formatScoreValue(sourceScore)
                    + "; topic_affinity=" + formatScoreValue(topicScore)
                    + "; format_affinity=" + formatScoreValue(formatScore)
                    + "; practical=" + formatScoreValue(input.practicalEngineeringScore())
                    + "; depth=" + formatScoreValue(input.technicalDepthScore())
                    + "; recency=" + formatScoreValue(roundToThreeDecimals(recencyScore));
            results.put(input.postId(), new RankingResult(input.postId(), total, explanation));
        }
        return results;
    }

    private ParsedAnalysis parseAnalysis(String metadataJson, String summaryRu) {
        if (metadataJson == null || metadataJson.isBlank()) {
            return new ParsedAnalysis(summaryRu, List.of(), null, null, null, null, null);
        }
        try {
            JsonNode metadata = objectMapper.readTree(metadataJson);
            List<String> topics = new ArrayList<>();
            JsonNode topicsNode = metadata.get("topics");
            if (topicsNode != null && topicsNode.isArray()) {
                topicsNode.forEach(node -> topics.add(node.asString()));
            }
            return new ParsedAnalysis(
                    summaryRu,
                    List.copyOf(topics),
                    textOrNull(metadata.get("format")),
                    textOrNull(metadata.get("technical_depth")),
                    textOrNull(metadata.get("verdict")),
                    textOrNull(metadata.get("verdict_reason")),
                    metadata.hasNonNull("relevance_score")
                            ? metadata.get("relevance_score").asInt()
                            : null);
        } catch (Exception exception) {
            return new ParsedAnalysis(summaryRu, List.of(), null, null, null, null, null);
        }
    }

    private String textOrNull(JsonNode node) {
        return node == null || node.isNull() ? null : node.asString();
    }

    private String formatInstant(OffsetDateTime value) {
        return value == null
                ? null
                : value.withOffsetSameInstant(ZoneOffset.UTC).toInstant().toString();
    }

    private String emptyToNull(String value) {
        return value == null || value.isEmpty() ? null : value;
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private String formatScoreValue(double value) {
        DecimalFormat format = new DecimalFormat("0.0##", DecimalFormatSymbols.getInstance(Locale.US));
        format.setGroupingUsed(false);
        return format.format(value);
    }

    private double roundToThreeDecimals(double value) {
        return BigDecimal.valueOf(value).setScale(3, RoundingMode.HALF_UP).doubleValue();
    }

    private long numberToLong(Object value) {
        return value instanceof Number number ? number.longValue() : Long.parseLong(String.valueOf(value));
    }

    private double feedbackWeight(String feedbackState) {
        if (feedbackState == null) {
            return 0.0;
        }
        return FEEDBACK_WEIGHTS.getOrDefault(feedbackState, 0.0);
    }

    private boolean booleanValue(Object value) {
        if (value == null) {
            return false;
        }
        if (value instanceof Boolean booleanValue) {
            return booleanValue;
        }
        if (value instanceof Number number) {
            return number.intValue() != 0;
        }
        return Boolean.parseBoolean(String.valueOf(value));
    }

    private OffsetDateTime offsetDateTime(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof OffsetDateTime offsetDateTime) {
            return offsetDateTime;
        }
        if (value instanceof Instant instant) {
            return instant.atOffset(ZoneOffset.UTC);
        }
        if (value instanceof ZonedDateTime zonedDateTime) {
            return zonedDateTime.toOffsetDateTime();
        }
        if (value instanceof LocalDateTime localDateTime) {
            return localDateTime.atOffset(ZoneOffset.UTC);
        }
        return OffsetDateTime.parse(String.valueOf(value));
    }

    private record FeedQuery(
            Long sourceId,
            String feedbackState,
            Boolean readLater,
            OffsetDateTime minPublishedAt,
            OffsetDateTime maxPublishedAt) {}

    public record DigestCandidate(
            long postId,
            String title,
            String sourceName,
            String canonicalUrl,
            String summaryRu,
            String verdict,
            String verdictReason,
            Integer relevanceScore) {}

    private record PostRow(
            long id,
            long sourceId,
            String sourceName,
            String canonicalUrl,
            String title,
            OffsetDateTime publishedAt,
            String rawContent,
            String feedbackState,
            boolean readLater,
            String summaryRu,
            String analysisMetadataJson) {}

    private record ParsedAnalysis(
            String summaryRu,
            List<String> topics,
            String format,
            String technicalDepth,
            String verdict,
            String verdictReason,
            Integer relevanceScore) {}

    private record RankablePost(
            long postId,
            String title,
            String sourceName,
            String canonicalUrl,
            OffsetDateTime publishedAt,
            String rawContent,
            String feedbackState,
            ParsedAnalysis analysis) {}

    private record RankInput(
            long postId,
            String sourceName,
            long publishedEpoch,
            String feedbackState,
            List<String> topics,
            String format,
            double practicalEngineeringScore,
            double technicalDepthScore) {}

    private record RankingResult(long postId, double score, String explanation) {}
}
