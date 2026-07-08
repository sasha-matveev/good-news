package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.dto.SettingsDtos;
import com.goodnews.backendjava.service.TestEmailService;
import com.goodnews.backendjava.service.SettingsService;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@Validated
@RestController
public class SettingsController {

    private final SettingsService settingsService;
    private final TestEmailService testEmailService;

    public SettingsController(SettingsService settingsService, TestEmailService testEmailService) {
        this.settingsService = settingsService;
        this.testEmailService = testEmailService;
    }

    @GetMapping("/api/settings")
    public Mono<SettingsDtos.SettingsResponse> getSettings() {
        return settingsService.getSettingsResponse();
    }

    @PutMapping("/api/settings")
    public Mono<SettingsDtos.SettingsResponse> updateSettings(@Valid @RequestBody SettingsDtos.SettingsUpdateRequest request) {
        return settingsService.updateSettings(request);
    }

    @PostMapping("/api/settings/test-email")
    public Mono<java.util.Map<String, String>> sendTestEmail() {
        return testEmailService.sendTestEmail();
    }
}
