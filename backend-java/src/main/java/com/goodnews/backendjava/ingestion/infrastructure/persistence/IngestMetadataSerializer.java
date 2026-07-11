package com.goodnews.backendjava.ingestion.infrastructure.persistence;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import java.time.Instant;
import org.springframework.stereotype.Component;

@Component
final class IngestMetadataSerializer {
    private final ObjectMapper objectMapper;

    IngestMetadataSerializer(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    String serialize(SourceDefinition source, CandidatePost post, Instant synchronizedAt) {
        try {
            return objectMapper.writeValueAsString(new Metadata(
                    post.publicationDateSource().persistedValue(),
                    source.strategyKind().persistedValue(),
                    synchronizedAt.toString()));
        } catch (JsonProcessingException error) {
            throw new IllegalStateException("Unable to serialize ingest metadata", error);
        }
    }

    private record Metadata(String date_source, String source_strategy, String synced_at) {}
}
