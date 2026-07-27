package com.goodnews.backendjava.analysis.infrastructure.persistence;

import com.goodnews.backendjava.analysis.application.port.AnalysisContextQuery;
import com.goodnews.backendjava.analysis.model.AnalysisContext;
import com.goodnews.backendjava.api.dto.PreferenceDtos;
import com.goodnews.backendjava.service.PreferenceService;
import com.goodnews.backendjava.service.SettingsService;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

@Component
public final class R2dbcAnalysisContextQuery implements AnalysisContextQuery {
    private final SettingsService settings;
    private final PreferenceService preferences;

    public R2dbcAnalysisContextQuery(SettingsService settings, PreferenceService preferences) {
        this.settings = settings;
        this.preferences = preferences;
    }

    @Override
    public Mono<AnalysisContext> load() {
        return Mono.zip(settings.loadSettings(), preferences.loadCurrentPreferenceProfile())
                .map(tuple -> {
                    SettingsService.AppSettings configured = tuple.getT1();
                    return new AnalysisContext(
                            configured.analysisSummaryPrompt(),
                            configured.analysisVerdictReasonPrompt(),
                            preferenceContext(tuple.getT2()));
                });
    }

    private String preferenceContext(PreferenceDtos.PreferenceProfileResponse profile) {
        if (profile.feedback_totals().total() == 0) {
            return "";
        }
        List<String> lines = new ArrayList<>();
        lines.add(profile.summary());
        if (!profile.positive_signals().isEmpty()) {
            lines.add("Likes: " + String.join("; ", profile.positive_signals()));
        }
        if (!profile.negative_signals().isEmpty()) {
            lines.add("Avoids: " + String.join("; ", profile.negative_signals()));
        }
        return String.join("\n", lines);
    }
}
