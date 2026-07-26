package com.goodnews.backendjava.service;

import com.goodnews.backendjava.api.dto.PreferenceDtos;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import reactor.core.publisher.Mono;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Service
public class PreferenceService {

    private final DatabaseClient databaseClient;
    private final ObjectMapper objectMapper;

    public PreferenceService(DatabaseClient databaseClient, ObjectMapper objectMapper) {
        this.databaseClient = databaseClient;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public Mono<PreferenceDtos.PreferenceProfileResponse> recomputePreferenceProfile() {
        return loadCurrentPreferenceProfile()
                .flatMap(profile -> persistPreferenceProfile(profile).thenReturn(profile));
    }

    public Mono<PreferenceDtos.PreferenceProfileResponse> loadCurrentPreferenceProfile() {
        return databaseClient
                .sql(
                        """
                SELECT s.display_name AS source_name, f.state AS feedback_state, pa.metadata_json
                FROM feedback f
                LEFT JOIN post_analysis pa ON pa.post_id = f.post_id
                JOIN posts p ON p.id = f.post_id
                JOIN sources s ON s.id = p.source_id
                """)
                .map((row, metadata) -> new PreferenceRow(
                        row.get("source_name", String.class),
                        row.get("feedback_state", String.class),
                        row.get("metadata_json", String.class)))
                .all()
                .collectList()
                .map(this::buildProfile);
    }

    private Mono<Void> persistPreferenceProfile(PreferenceDtos.PreferenceProfileResponse profile) {
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("positive_signals", profile.positive_signals());
        metadata.put("negative_signals", profile.negative_signals());
        metadata.put("learning_proof", profile.learning_proof());
        metadata.put(
                "feedback_totals",
                Map.of(
                        "interesting", profile.feedback_totals().interesting(),
                        "want_to_read", profile.feedback_totals().want_to_read(),
                        "not_interesting", profile.feedback_totals().not_interesting(),
                        "total", profile.feedback_totals().total()));
        try {
            String metadataJson = objectMapper.writeValueAsString(metadata);
            return databaseClient
                    .sql(
                            """
                    INSERT INTO preference_profile (id, summary, metadata_json, updated_at)
                    VALUES (1, :summary, :metadataJson, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE
                    SET summary = EXCLUDED.summary,
                        metadata_json = EXCLUDED.metadata_json,
                        updated_at = CURRENT_TIMESTAMP
                    """)
                    .bind("summary", profile.summary())
                    .bind("metadataJson", metadataJson)
                    .fetch()
                    .rowsUpdated()
                    .then();
        } catch (Exception exception) {
            return Mono.error(exception);
        }
    }

    private PreferenceDtos.PreferenceProfileResponse buildProfile(List<PreferenceRow> rows) {
        Map<String, Integer> sourceCounts = new HashMap<>();
        Map<String, Integer> topicCounts = new HashMap<>();
        Map<String, Integer> formatCounts = new HashMap<>();
        Map<String, Integer> depthCounts = new HashMap<>();
        Map<String, Integer> negativeTopicCounts = new HashMap<>();
        Map<String, Integer> negativeFormatCounts = new HashMap<>();
        PreferenceDtos.PreferenceFeedbackTotalsResponse feedbackTotals =
                new PreferenceDtos.PreferenceFeedbackTotalsResponse(0, 0, 0, 0);

        int total = 0;
        int interesting = 0;
        int wantToRead = 0;
        int notInteresting = 0;

        for (PreferenceRow row : rows) {
            JsonNode metadata = parseMetadata(row.metadataJson());
            String feedbackState = row.feedbackState();
            if ("interesting".equals(feedbackState)) {
                interesting++;
                total++;
            } else if ("want_to_read".equals(feedbackState)) {
                wantToRead++;
                total++;
            } else if ("not_interesting".equals(feedbackState)) {
                notInteresting++;
                total++;
            }

            if ("interesting".equals(feedbackState) || "want_to_read".equals(feedbackState)) {
                sourceCounts.merge(defaultIfBlank(row.sourceName(), "Unknown source"), 1, Integer::sum);
                metadata.path("topics").forEach(topic -> topicCounts.merge(topic.asString(), 1, Integer::sum));
                String format = textOrNull(metadata.get("format"));
                if (format != null) {
                    formatCounts.merge(format, 1, Integer::sum);
                }
                String technicalDepth = textOrNull(metadata.get("technical_depth"));
                if (technicalDepth != null && !"null".equals(technicalDepth)) {
                    depthCounts.merge(technicalDepth, 1, Integer::sum);
                }
            }

            if ("not_interesting".equals(feedbackState)) {
                metadata.path("topics").forEach(topic -> negativeTopicCounts.merge(topic.asString(), 1, Integer::sum));
                String format = textOrNull(metadata.get("format"));
                if (format != null) {
                    negativeFormatCounts.merge(format, 1, Integer::sum);
                }
            }
        }

        feedbackTotals =
                new PreferenceDtos.PreferenceFeedbackTotalsResponse(total, interesting, wantToRead, notInteresting);
        CountedSignal topSource = topSignal(sourceCounts);
        CountedSignal topTopic = topSignal(topicCounts);
        CountedSignal topFormat = topSignal(formatCounts);
        CountedSignal topDepth = topSignal(depthCounts);
        CountedSignal topNegativeTopic = topSignal(negativeTopicCounts);
        CountedSignal topNegativeFormat = topSignal(negativeFormatCounts);

        List<String> positiveSignals = new ArrayList<>();
        if (topSource != null) {
            positiveSignals.add(topSource.count() + " " + countLabel(topSource.count(), "positive signal")
                    + " for source " + topSource.key());
        }
        if (topTopic != null) {
            positiveSignals.add(topTopic.count() + " " + countLabel(topTopic.count(), "positive signal") + " for topic "
                    + topicPhrase(topTopic.key()));
        }
        if (topFormat != null) {
            positiveSignals.add(topFormat.count() + " " + countLabel(topFormat.count(), "positive signal")
                    + " for format " + topFormat.key());
        }
        if (topDepth != null) {
            positiveSignals.add(topDepth.count() + " " + countLabel(topDepth.count(), "positive signal") + " for "
                    + topDepth.key() + " technical material");
        }

        List<String> negativeSignals = new ArrayList<>();
        if (topNegativeTopic != null) {
            negativeSignals.add(
                    topNegativeTopic.count() + " " + countLabel(topNegativeTopic.count(), "not-interesting signal")
                            + " against topic " + topicPhrase(topNegativeTopic.key()));
        }
        if (topNegativeFormat != null) {
            negativeSignals.add(
                    topNegativeFormat.count() + " " + countLabel(topNegativeFormat.count(), "not-interesting signal")
                            + " against format " + topNegativeFormat.key());
        }

        List<String> learningProof = new ArrayList<>();
        String summary;
        if (feedbackTotals.total() == 0) {
            summary = "No feedback yet. Save reactions from the feed to teach this profile what to prioritize.";
            learningProof.add("0 feedback decisions recorded yet.");
        } else {
            learningProof.add(feedbackTotals.total() + " feedback decisions recorded: "
                    + feedbackTotals.interesting() + " interesting, "
                    + feedbackTotals.want_to_read() + " want to read, "
                    + feedbackTotals.not_interesting() + " not interesting.");
            List<String> strongestPositiveParts = new ArrayList<>();
            if (topSource != null) {
                strongestPositiveParts.add("source " + topSource.key());
            }
            if (topTopic != null) {
                strongestPositiveParts.add("topic " + topicPhrase(topTopic.key()));
            }
            if (!strongestPositiveParts.isEmpty()) {
                learningProof.add("Strongest positive pull: " + String.join(" and ", strongestPositiveParts) + ".");
            }

            List<String> strongestNegativeParts = new ArrayList<>();
            if (topNegativeTopic != null) {
                strongestNegativeParts.add("topic " + topicPhrase(topNegativeTopic.key()));
            }
            if (topNegativeFormat != null) {
                strongestNegativeParts.add("format " + topNegativeFormat.key());
            }
            if (!strongestNegativeParts.isEmpty()) {
                learningProof.add("Strongest negative pull: " + String.join(" and ", strongestNegativeParts) + ".");
            }

            String positiveFocus = "";
            if (topTopic != null && topFormat != null && topSource != null) {
                positiveFocus = "toward " + topicPhrase(topTopic.key()) + " " + formatPlural(topFormat.key()) + " from "
                        + topSource.key();
            } else if (topTopic != null) {
                positiveFocus = "toward " + topicPhrase(topTopic.key()) + " coverage";
            } else if (topSource != null) {
                positiveFocus = "toward work from " + topSource.key();
            }

            String negativeFocus = "";
            if (topNegativeFormat != null) {
                negativeFocus = "away from " + formatPlural(topNegativeFormat.key());
            } else if (topNegativeTopic != null) {
                negativeFocus = "away from " + topicPhrase(topNegativeTopic.key()) + " coverage";
            }

            List<String> summaryParts = new ArrayList<>();
            summaryParts.add("From " + feedbackTotals.total() + " feedback signals, the profile is learning");
            if (!positiveFocus.isEmpty()) {
                summaryParts.add(positiveFocus);
            }
            if (!negativeFocus.isEmpty()) {
                summaryParts.add(positiveFocus.isEmpty() ? negativeFocus : "and " + negativeFocus);
            }
            summary = String.join(" ", summaryParts).trim() + ".";
        }

        return new PreferenceDtos.PreferenceProfileResponse(
                summary,
                List.copyOf(positiveSignals),
                List.copyOf(negativeSignals),
                List.copyOf(learningProof),
                feedbackTotals);
    }

    private JsonNode parseMetadata(String metadataJson) {
        try {
            if (metadataJson == null || metadataJson.isBlank()) {
                return objectMapper.createObjectNode();
            }
            return objectMapper.readTree(metadataJson);
        } catch (Exception exception) {
            return objectMapper.createObjectNode();
        }
    }

    private CountedSignal topSignal(Map<String, Integer> counts) {
        return counts.entrySet().stream()
                .min(Comparator.<Map.Entry<String, Integer>>comparingInt(entry -> -entry.getValue())
                        .thenComparing(Map.Entry::getKey))
                .map(entry -> new CountedSignal(entry.getKey(), entry.getValue()))
                .orElse(null);
    }

    private String topicPhrase(String topic) {
        return topic == null ? null : topic.replace("-", " ");
    }

    private String formatPlural(String formatName) {
        if (formatName == null) {
            return null;
        }
        if ("opinion".equals(formatName)) {
            return "opinion pieces";
        }
        if (formatName.endsWith("s")) {
            return formatName;
        }
        return formatName + "s";
    }

    private String countLabel(int count, String singular) {
        return count == 1 ? singular : singular + "s";
    }

    private String textOrNull(JsonNode node) {
        return node == null || node.isNull() ? null : node.asString();
    }

    private String defaultIfBlank(String value, String defaultValue) {
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        return value;
    }

    private record PreferenceRow(String sourceName, String feedbackState, String metadataJson) {}

    private record CountedSignal(String key, int count) {}
}
