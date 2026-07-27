package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.dto.PreferenceDtos;
import com.goodnews.backendjava.service.PreferenceService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@RestController
public class PreferencesController {

    private final PreferenceService preferenceService;

    public PreferencesController(PreferenceService preferenceService) {
        this.preferenceService = preferenceService;
    }

    @GetMapping("/api/preferences")
    public Mono<PreferenceDtos.PreferenceProfileResponse> getPreferences() {
        return preferenceService.recomputePreferenceProfile();
    }

    @PostMapping("/api/preferences/recompute")
    public Mono<PreferenceDtos.PreferenceProfileResponse> recomputePreferences() {
        return preferenceService.recomputePreferenceProfile();
    }
}
