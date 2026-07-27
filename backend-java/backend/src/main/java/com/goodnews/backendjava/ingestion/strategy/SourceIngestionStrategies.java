package com.goodnews.backendjava.ingestion.strategy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public final class SourceIngestionStrategies {
    private final Map<SourceStrategyKind, SourceIngestionStrategy> strategies;

    public SourceIngestionStrategies(List<SourceIngestionStrategy> strategies) {
        Map<SourceStrategyKind, SourceIngestionStrategy> indexed = new EnumMap<>(SourceStrategyKind.class);
        for (SourceIngestionStrategy strategy : strategies) {
            if (indexed.put(strategy.kind(), strategy) != null) {
                throw new IllegalStateException("Duplicate source strategy " + strategy.kind());
            }
        }
        this.strategies = Map.copyOf(indexed);
    }

    public SourceIngestionStrategy resolve(SourceStrategyKind kind) {
        SourceIngestionStrategy strategy = strategies.get(kind);
        if (strategy == null) {
            throw new SourceIngestionException("Unsupported source strategy " + kind);
        }
        return strategy;
    }
}
