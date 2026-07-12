package com.goodnews.backendjava.api.dto;

import com.goodnews.backendjava.validation.ValidDigestDayOfWeek;
import com.goodnews.backendjava.validation.ValidSmtpSecurityMode;
import com.goodnews.backendjava.validation.ValidTwentyFourHourTime;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public final class SettingsDtos {

    private SettingsDtos() {}

    public record SettingsResponse(
            String daily_digest_time,
            String weekly_digest_day_of_week,
            String weekly_digest_time,
            String observability_dashboard_url,
            String recipient_email,
            String sender_identity,
            String smtp_host,
            int smtp_port,
            String smtp_username,
            String smtp_security_mode,
            boolean daily_digest_enabled,
            boolean daily_digest_catch_up_enabled,
            boolean weekly_digest_enabled,
            boolean weekly_digest_catch_up_enabled,
            boolean smtp_password_configured,
            String analysis_summary_prompt,
            String analysis_verdict_reason_prompt) {}

    public record SettingsUpdateRequest(
            @NotNull @ValidTwentyFourHourTime(fieldName = "daily_digest_time") String daily_digest_time,
            @NotNull @ValidDigestDayOfWeek String weekly_digest_day_of_week,
            @NotNull @ValidTwentyFourHourTime(fieldName = "weekly_digest_time") String weekly_digest_time,
            String recipient_email,
            String sender_identity,
            String smtp_host,
            @NotNull @Min(1) @Max(65535) Integer smtp_port,
            String smtp_username,
            @NotNull @ValidSmtpSecurityMode String smtp_security_mode,
            Boolean daily_digest_enabled,
            Boolean daily_digest_catch_up_enabled,
            Boolean weekly_digest_enabled,
            Boolean weekly_digest_catch_up_enabled,
            String smtp_password,
            @Size(max = 8000, message = "prompt must be at most 8000 characters") String analysis_summary_prompt,
            @Size(max = 8000, message = "prompt must be at most 8000 characters")
                    String analysis_verdict_reason_prompt) {
        public Boolean daily_digest_enabled() {
            return daily_digest_enabled == null ? Boolean.TRUE : daily_digest_enabled;
        }

        public Boolean daily_digest_catch_up_enabled() {
            return daily_digest_catch_up_enabled == null ? Boolean.TRUE : daily_digest_catch_up_enabled;
        }

        public Boolean weekly_digest_enabled() {
            return weekly_digest_enabled == null ? Boolean.FALSE : weekly_digest_enabled;
        }

        public Boolean weekly_digest_catch_up_enabled() {
            return weekly_digest_catch_up_enabled == null ? Boolean.TRUE : weekly_digest_catch_up_enabled;
        }

        public String normalizedDailyDigestTime() {
            return normalizeTime(daily_digest_time);
        }

        public String normalizedWeeklyDigestTime() {
            return normalizeTime(weekly_digest_time);
        }

        public String normalizedWeeklyDigestDayOfWeek() {
            return weekly_digest_day_of_week == null
                    ? null
                    : weekly_digest_day_of_week.trim().toLowerCase();
        }

        private static String normalizeTime(String value) {
            if (value == null) {
                return null;
            }
            String[] parts = value.split(":");
            int hour = Integer.parseInt(parts[0]);
            int minute = Integer.parseInt(parts[1]);
            return "%02d:%02d".formatted(hour, minute);
        }
    }
}
