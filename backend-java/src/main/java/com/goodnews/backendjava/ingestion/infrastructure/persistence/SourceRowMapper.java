package com.goodnews.backendjava.ingestion.infrastructure.persistence;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import com.goodnews.backendjava.ingestion.model.SourceStrategyOptions;
import io.r2dbc.spi.Row;
import java.time.OffsetDateTime;
import org.springframework.stereotype.Component;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Component
final class SourceRowMapper {
    private final ObjectMapper objectMapper;

    SourceRowMapper(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    SourceDefinition map(Row row) {
        Long id = row.get("id", Long.class);
        OffsetDateTime lastSuccess = row.get("last_success_at", OffsetDateTime.class);
        return new SourceDefinition(
                id,
                row.get("original_url", String.class),
                row.get("feed_url", String.class),
                strategy(row.get("strategy_kind", String.class)),
                options(row.get("strategy_config", String.class)),
                lastSuccess == null ? null : lastSuccess.toInstant());
    }

    private SourceStrategyKind strategy(String value) {
        try {
            return SourceStrategyKind.fromPersistedValue(value);
        } catch (IllegalArgumentException error) {
            throw new SourceIngestionException(error.getMessage(), error);
        }
    }

    private SourceStrategyOptions options(String value) {
        try {
            JsonNode root = objectMapper.readTree(value == null || value.isBlank() ? "{}" : value);
            return new SourceStrategyOptions(
                    text(root, "listing_url"), text(root, "link_selector"), text(root, "parser_id"));
        } catch (JacksonException error) {
            throw new SourceIngestionException("Invalid source strategy configuration", error);
        }
    }

    private static String text(JsonNode root, String field) {
        String value = root.path(field).asString("");
        return value.isBlank() ? null : value;
    }
}
