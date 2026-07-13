package com.goodnews.backendjava.analysis.infrastructure.gemini;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import org.junit.jupiter.api.Test;

class AnalysisPayloadNormalizerTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final AnalysisPayloadNormalizer normalizer = new AnalysisPayloadNormalizer(objectMapper);

    @Test
    void preservesPythonAliasesCoercionLanguagesEnumsAndScoreClamp() throws Exception {
        AnalysisResult result = normalizer.normalize(
                7,
                objectMapper.readTree(
                        """
                {"summary":"English snake_case garbage","topics":"Java","format":"UNKNOWN",
                 "technical_depth":"ADVANCED","verdict":"maybe","verdict_reason":"Причина только по-русски",
                 "relevance_score":99}
                """));

        assertThat(result.summaryRu()).isEmpty();
        assertThat(result.topics()).containsExactly("Java");
        assertThat(result.format()).isEmpty();
        assertThat(result.technicalDepth()).isEqualTo("advanced");
        assertThat(result.verdict()).isEmpty();
        assertThat(result.verdictReason()).isEmpty();
        assertThat(result.relevanceScore()).isEqualTo(10);
    }

    @Test
    void rejectsLettersOutsideExactPythonAllowedCodePointRanges() throws Exception {
        AnalysisResult result = normalizer.normalize(
                8,
                objectMapper.readTree(
                        """
                {"summary_ru":"Резюме Ḁ","topics":[],"format":"news","technical_depth":"beginner",
                "verdict":"interesting","verdict_reason":"Useful."}
                """));

        assertThat(result.summaryRu()).isEmpty();
    }
}
