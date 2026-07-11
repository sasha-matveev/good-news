package com.goodnews.backendjava.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.api.dto.MonitoringDtos;
import com.goodnews.backendjava.api.dto.PreferenceDtos;
import com.goodnews.backendjava.api.dto.PostDtos;
import com.goodnews.backendjava.api.dto.SettingsDtos;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class DtoContractTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private Validator validator;

    @BeforeEach
    void setUp() {
        validator = Validation.buildDefaultValidatorFactory().getValidator();
    }

    @Test
    void postResponseSerializesUsingPythonCompatibleFieldNames() throws Exception {
        PostDtos.PostResponse response = new PostDtos.PostResponse(
            1L,
            2L,
            "Example",
            "https://example.com/post",
            "Title",
            "2026-05-14T12:00:00Z",
            "feed",
            "Body",
            "interesting",
            true,
            "Summary",
            "keep",
            "Useful",
            87,
            "Ranked high"
        );

        assertThat(objectMapper.writeValueAsString(response)).isEqualTo(
            "{\"id\":1,\"source_id\":2,\"source_name\":\"Example\",\"canonical_url\":\"https://example.com/post\","
                + "\"title\":\"Title\",\"published_at\":\"2026-05-14T12:00:00Z\",\"published_at_source\":\"feed\","
                + "\"raw_content\":\"Body\",\"feedback_state\":\"interesting\",\"read_later\":true,"
                + "\"summary_ru\":\"Summary\",\"verdict\":\"keep\",\"verdict_reason\":\"Useful\","
                + "\"relevance_score\":87,\"ranking_explanation\":\"Ranked high\"}"
        );
    }

    @Test
    void monitoringSummarySerializesNestedServices() throws Exception {
        MonitoringDtos.MonitoringSummaryResponse response = new MonitoringDtos.MonitoringSummaryResponse(
            2,
            3,
            10,
            4,
            "2026-05-14T12:00:00Z",
            Map.of("content_api", "ok", "analysis_llm", "error")
        );

        assertThat(objectMapper.readValue(objectMapper.writeValueAsBytes(response), Map.class))
            .containsEntry("sources_active", 2)
            .containsEntry("last_sync_at", "2026-05-14T12:00:00Z");
    }

    @Test
    void preferenceProfileResponseSerializesPythonCompatibleFieldNames() throws Exception {
        PreferenceDtos.PreferenceProfileResponse response = new PreferenceDtos.PreferenceProfileResponse(
            "Summary",
            java.util.List.of("Positive"),
            java.util.List.of("Negative"),
            java.util.List.of("Proof"),
            new PreferenceDtos.PreferenceFeedbackTotalsResponse(3, 1, 1, 1)
        );

        assertThat(objectMapper.writeValueAsString(response)).isEqualTo(
            "{\"summary\":\"Summary\",\"positive_signals\":[\"Positive\"],\"negative_signals\":[\"Negative\"],"
                + "\"learning_proof\":[\"Proof\"],\"feedback_totals\":{\"total\":3,\"interesting\":1,"
                + "\"want_to_read\":1,\"not_interesting\":1}}"
        );
    }

    @Test
    void settingsUpdateRequestMatchesFastApiValidationMessagesAndNormalization() {
        SettingsDtos.SettingsUpdateRequest request = new SettingsDtos.SettingsUpdateRequest(
            "25:99",
            "funday",
            "24:15",
            null,
            null,
            null,
            70000,
            null,
            "tls",
            true,
            true,
            false,
            true,
            null,
            "x".repeat(8001),
            ""
        );

        Set<ConstraintViolation<SettingsDtos.SettingsUpdateRequest>> violations = validator.validate(request);

        assertThat(violations).extracting(ConstraintViolation::getMessage).contains(
            "daily_digest_time must use HH:MM format",
            "weekly_digest_day_of_week must be one of mon, tue, wed, thu, fri, sat, sun",
            "weekly_digest_time must use HH:MM format",
            "must be less than or equal to 65535",
            "smtp_security_mode must be one of none, starttls, ssl",
            "prompt must be at most 8000 characters"
        );
    }

    @Test
    void settingsUpdateRequestNormalizesAcceptedScheduleFields() {
        SettingsDtos.SettingsUpdateRequest request = new SettingsDtos.SettingsUpdateRequest(
            "8:5",
            " FRI ",
            "16:3",
            null,
            null,
            null,
            587,
            null,
            "starttls",
            true,
            true,
            false,
            true,
            null,
            "",
            ""
        );

        assertThat(validator.validate(request)).isEmpty();
        assertThat(request.normalizedDailyDigestTime()).isEqualTo("08:05");
        assertThat(request.normalizedWeeklyDigestTime()).isEqualTo("16:03");
        assertThat(request.normalizedWeeklyDigestDayOfWeek()).isEqualTo("fri");
    }

    @Test
    void settingsUpdateRequestRejectsMissingRequiredFields() {
        SettingsDtos.SettingsUpdateRequest request = new SettingsDtos.SettingsUpdateRequest(
            "12:00",
            "fri",
            "16:30",
            null,
            null,
            null,
            null,
            null,
            "starttls",
            null,
            null,
            null,
            null,
            null,
            "",
            ""
        );

        assertThat(validator.validate(request)).extracting(ConstraintViolation::getMessage).contains(
            "must not be null"
        );
    }

    @Test
    void settingsUpdateRequestDefaultsOmittedDigestBooleansLikePython() {
        SettingsDtos.SettingsUpdateRequest request = new SettingsDtos.SettingsUpdateRequest(
            "12:00",
            "fri",
            "16:30",
            null,
            null,
            null,
            587,
            null,
            "starttls",
            null,
            null,
            null,
            null,
            null,
            "",
            ""
        );

        assertThat(validator.validate(request)).isEmpty();
        assertThat(request.daily_digest_enabled()).isTrue();
        assertThat(request.daily_digest_catch_up_enabled()).isTrue();
        assertThat(request.weekly_digest_enabled()).isFalse();
        assertThat(request.weekly_digest_catch_up_enabled()).isTrue();
    }
}
