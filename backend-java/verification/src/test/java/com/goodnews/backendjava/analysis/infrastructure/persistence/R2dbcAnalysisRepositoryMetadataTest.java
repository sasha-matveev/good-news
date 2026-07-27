package com.goodnews.backendjava.analysis.infrastructure.persistence;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.analysis.model.AnalysisResult;
import java.util.List;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class R2dbcAnalysisRepositoryMetadataTest {
    @Test
    void mapsEveryAnalysisFieldToPythonCompatibleMetadataKeys() throws Exception {
        ObjectMapper objectMapper = new ObjectMapper();
        R2dbcAnalysisRepository repository = new R2dbcAnalysisRepository(null, null, objectMapper);
        AnalysisResult result =
                new AnalysisResult(3, "Резюме", List.of("Java"), "tutorial", "advanced", "interesting", "Useful", 9);

        assertThat(objectMapper.readTree(repository.metadata(result)))
                .isEqualTo(
                        objectMapper.readTree(
                                """
                {"topics":["Java"],"format":"tutorial","technical_depth":"advanced",
                "verdict":"interesting","verdict_reason":"Useful","relevance_score":9}
                """));
    }
}
