package com.goodnews.backendjava.analysis.infrastructure.gemini;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

final class AnalysisPayloadNormalizer {
    private static final Set<String> VERDICTS = Set.of("interesting", "not_interesting");
    private static final Set<String> FORMATS =
            Set.of("tutorial", "opinion", "news", "case-study", "announcement", "other");
    private static final Set<String> DEPTHS = Set.of("beginner", "intermediate", "advanced");
    private static final Pattern SNAKE_CASE = Pattern.compile("\\w+_\\w+");

    private final ObjectMapper objectMapper;

    AnalysisPayloadNormalizer(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    AnalysisResult normalize(long postId, JsonNode value) {
        if (!value.isObject()) {
            throw new IllegalArgumentException("Gemini analysis must be a JSON object");
        }
        JsonNode summaryNode = value.has("summary_ru") ? value.get("summary_ru") : required(value, "summary");
        String summary = asContractString(summaryNode);
        if (!mostlyCyrillic(summary)) {
            summary = "";
        }
        String verdict = asContractString(required(value, "verdict"));
        if (!VERDICTS.contains(verdict)) {
            verdict = "";
        }
        String format = asContractString(required(value, "format")).toLowerCase();
        if (!FORMATS.contains(format)) {
            format = "";
        }
        String depth = asContractString(required(value, "technical_depth")).toLowerCase();
        if (!DEPTHS.contains(depth)) {
            depth = "";
        }
        String reason = asContractString(required(value, "verdict_reason"));
        if (latinCount(reason) < cyrillicCount(reason)) {
            reason = "";
        }
        return new AnalysisResult(
                postId,
                summary,
                topics(required(value, "topics")),
                format,
                depth,
                verdict,
                reason,
                score(value.get("relevance_score")));
    }

    private JsonNode required(JsonNode value, String field) {
        JsonNode node = value.get(field);
        if (node == null) {
            throw new IllegalArgumentException("Gemini response missing required field: " + field);
        }
        return node;
    }

    private List<String> topics(JsonNode value) {
        List<String> topics = new ArrayList<>();
        if (value.isArray()) {
            value.forEach(item -> topics.add(asContractString(item)));
        } else {
            topics.add(asContractString(value));
        }
        return List.copyOf(topics);
    }

    private int score(JsonNode value) {
        if (value == null || value.isNull() || value.isBoolean() || value.isContainerNode()) {
            return 0;
        }
        try {
            long rounded = new BigDecimal(value.asText())
                    .setScale(0, java.math.RoundingMode.HALF_EVEN)
                    .longValue();
            return (int) Math.max(0, Math.min(10, rounded));
        } catch (NumberFormatException exception) {
            return 0;
        }
    }

    private String asContractString(JsonNode value) {
        if (value == null || value.isNull()) {
            return "";
        }
        if (value.isBoolean()) {
            return value.booleanValue() ? "True" : "False";
        }
        if (value.isTextual() || value.isNumber()) {
            return value.asText();
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalArgumentException("Gemini field is not serializable", exception);
        }
    }

    private boolean mostlyCyrillic(String text) {
        if (text.isEmpty()) {
            return true;
        }
        if (SNAKE_CASE.matcher(text).find()) {
            return false;
        }
        for (int offset = 0; offset < text.length(); ) {
            int codePoint = text.codePointAt(offset);
            offset += Character.charCount(codePoint);
            if (Character.isLetter(codePoint)
                    && !(codePoint <= 0x036F || (codePoint >= 0x0400 && codePoint <= 0x052F))) {
                return false;
            }
        }
        return cyrillicCount(text) >= latinCount(text);
    }

    private int cyrillicCount(String text) {
        return (int) text.codePoints()
                .filter(code -> code >= 0x0400 && code <= 0x052F)
                .count();
    }

    private int latinCount(String text) {
        return (int) text.codePoints()
                .filter(code -> (code >= 'A' && code <= 'Z') || (code >= 'a' && code <= 'z'))
                .count();
    }
}
