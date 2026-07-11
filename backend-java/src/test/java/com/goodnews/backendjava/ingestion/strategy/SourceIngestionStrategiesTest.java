package com.goodnews.backendjava.ingestion.strategy;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;

class SourceIngestionStrategiesTest {
    @Test
    void resolvesRegisteredStrategy() {
        StubStrategy strategy = new StubStrategy(SourceStrategyKind.FEED);
        assertThat(new SourceIngestionStrategies(List.of(strategy)).resolve(SourceStrategyKind.FEED))
                .isSameAs(strategy);
    }

    @Test
    void rejectsDuplicateRegistration() {
        assertThatThrownBy(() -> new SourceIngestionStrategies(
                        List.of(new StubStrategy(SourceStrategyKind.FEED), new StubStrategy(SourceStrategyKind.FEED))))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void rejectsUnknownKind() {
        assertThatThrownBy(() -> new SourceIngestionStrategies(List.of()).resolve(SourceStrategyKind.HTML))
                .isInstanceOf(SourceIngestionException.class);
    }

    private record StubStrategy(SourceStrategyKind kind) implements SourceIngestionStrategy {
        @Override
        public Mono<List<CandidatePost>> ingest(SourceDefinition source) {
            return Mono.just(List.of());
        }
    }
}
