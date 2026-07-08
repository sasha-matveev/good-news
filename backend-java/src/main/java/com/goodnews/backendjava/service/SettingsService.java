package com.goodnews.backendjava.service;

import com.goodnews.backendjava.api.dto.SettingsDtos;
import com.goodnews.backendjava.config.GoodNewsProperties;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Service
public class SettingsService {

    static final String DEFAULT_SUMMARY_INSTRUCTIONS = """
        a detailed summary in Russian (Кириллица), 4-6 sentences (roughly 60-120 words). Cover what the article is about, its key points, arguments or findings, and the concrete takeaway — enough that the reader understands the substance without opening the article. Do not just rephrase the title; add the specifics from the body. Use only Russian words — no Latin, no code, no transliteration. If you cannot write proper Russian, use "".
        """.strip();
    static final String DEFAULT_VERDICT_REASON_INSTRUCTIONS = """
        1 sentence in ENGLISH explaining why THIS reader (given the reader preference profile above, when present) would or would not want to read this. MUST be in English. No Russian.
        """.strip();

    private static final Map<String, String> DEFAULT_SETTINGS = Map.ofEntries(
        Map.entry("daily_digest_time", "12:00"),
        Map.entry("weekly_digest_day_of_week", "sat"),
        Map.entry("weekly_digest_time", "23:30"),
        Map.entry("smtp_port", "587"),
        Map.entry("smtp_security_mode", "starttls"),
        Map.entry("daily_digest_enabled", "true"),
        Map.entry("daily_digest_catch_up_enabled", "true"),
        Map.entry("weekly_digest_enabled", "false"),
        Map.entry("weekly_digest_catch_up_enabled", "true"),
        Map.entry("analysis_summary_prompt", DEFAULT_SUMMARY_INSTRUCTIONS),
        Map.entry("analysis_verdict_reason_prompt", DEFAULT_VERDICT_REASON_INSTRUCTIONS)
    );

    private final DatabaseClient databaseClient;
    private final GoodNewsProperties properties;

    public SettingsService(DatabaseClient databaseClient, GoodNewsProperties properties) {
        this.databaseClient = databaseClient;
        this.properties = properties;
    }

    public Mono<SettingsDtos.SettingsResponse> getSettingsResponse() {
        return loadSettings().map(this::toResponse);
    }

    @Transactional
    public Mono<SettingsDtos.SettingsResponse> updateSettings(SettingsDtos.SettingsUpdateRequest request) {
        AppSettingsUpdate update = new AppSettingsUpdate(
            request.normalizedDailyDigestTime(),
            request.normalizedWeeklyDigestDayOfWeek(),
            request.normalizedWeeklyDigestTime(),
            request.recipient_email(),
            request.sender_identity(),
            request.smtp_host(),
            request.smtp_port(),
            request.smtp_username(),
            request.smtp_security_mode(),
            request.daily_digest_enabled(),
            request.daily_digest_catch_up_enabled(),
            request.weekly_digest_enabled(),
            request.weekly_digest_catch_up_enabled(),
            request.smtp_password(),
            request.analysis_summary_prompt(),
            request.analysis_verdict_reason_prompt()
        );
        return saveSettings(update).map(this::toResponse);
    }

    public Mono<AppSettings> loadSettings() {
        Mono<Map<String, String>> storedSettings = databaseClient.sql("SELECT key, value FROM settings")
            .map((row, metadata) -> new StoredSettingRow(
                row.get("key", String.class),
                row.get("value", String.class)
            ))
            .all()
            .collectMap(StoredSettingRow::key, StoredSettingRow::value, LinkedHashMap::new);

        Mono<Map<String, Boolean>> secretSettings = databaseClient.sql("SELECT key FROM secret_settings")
            .map((row, metadata) -> row.get("key", String.class))
            .all()
            .collectMap(key -> key, key -> true, LinkedHashMap::new);

        return Mono.zip(storedSettings, secretSettings)
            .map(tuple -> {
                Map<String, String> stored = tuple.getT1();
                Map<String, Boolean> secrets = tuple.getT2();
                return new AppSettings(
                    stored.getOrDefault("daily_digest_time", DEFAULT_SETTINGS.get("daily_digest_time")),
                    stored.getOrDefault("weekly_digest_day_of_week", DEFAULT_SETTINGS.get("weekly_digest_day_of_week")),
                    stored.getOrDefault("weekly_digest_time", DEFAULT_SETTINGS.get("weekly_digest_time")),
                    stored.get("recipient_email"),
                    stored.get("sender_identity"),
                    stored.get("smtp_host"),
                    Integer.parseInt(stored.getOrDefault("smtp_port", DEFAULT_SETTINGS.get("smtp_port"))),
                    stored.get("smtp_username"),
                    stored.getOrDefault("smtp_security_mode", DEFAULT_SETTINGS.get("smtp_security_mode")),
                    asBoolean(stored.get("daily_digest_enabled"), true),
                    asBoolean(stored.get("daily_digest_catch_up_enabled"), true),
                    asBoolean(stored.get("weekly_digest_enabled"), false),
                    asBoolean(stored.get("weekly_digest_catch_up_enabled"), true),
                    secrets.containsKey("smtp_password"),
                    defaultIfBlank(stored.get("analysis_summary_prompt"), DEFAULT_SETTINGS.get("analysis_summary_prompt")),
                    defaultIfBlank(
                        stored.get("analysis_verdict_reason_prompt"),
                        DEFAULT_SETTINGS.get("analysis_verdict_reason_prompt")
                    )
                );
            });
    }

    public Mono<AppSettings> saveSettings(AppSettingsUpdate update) {
        Mono<Void> writes = Flux.concat(
                upsertSetting("daily_digest_time", update.dailyDigestTime()),
                upsertSetting("weekly_digest_day_of_week", update.weeklyDigestDayOfWeek()),
                upsertSetting("weekly_digest_time", update.weeklyDigestTime()),
                upsertSetting("recipient_email", update.recipientEmail()),
                upsertSetting("sender_identity", update.senderIdentity()),
                upsertSetting("smtp_host", update.smtpHost()),
                upsertSetting("smtp_port", Integer.toString(update.smtpPort())),
                upsertSetting("smtp_username", update.smtpUsername()),
                upsertSetting("smtp_security_mode", update.smtpSecurityMode()),
                upsertSetting("daily_digest_enabled", Boolean.toString(update.dailyDigestEnabled()).toLowerCase()),
                upsertSetting(
                    "daily_digest_catch_up_enabled",
                    Boolean.toString(update.dailyDigestCatchUpEnabled()).toLowerCase()
                ),
                upsertSetting("weekly_digest_enabled", Boolean.toString(update.weeklyDigestEnabled()).toLowerCase()),
                upsertSetting(
                    "weekly_digest_catch_up_enabled",
                    Boolean.toString(update.weeklyDigestCatchUpEnabled()).toLowerCase()
                ),
                upsertSetting("analysis_summary_prompt", blankToNull(update.analysisSummaryPrompt())),
                upsertSetting("analysis_verdict_reason_prompt", blankToNull(update.analysisVerdictReasonPrompt()))
            )
            .then();

        Mono<Void> secretWrite = hasText(update.smtpPassword())
            ? upsertSecretSetting("smtp_password", encryptSecret(update.smtpPassword(), requireAppMasterKey()))
            : Mono.empty();

        return writes.then(secretWrite).then(loadSettings());
    }

    public Mono<String> getSmtpPassword() {
        return databaseClient.sql("SELECT encrypted_value FROM secret_settings WHERE key = :key")
            .bind("key", "smtp_password")
            .map((row, metadata) -> row.get("encrypted_value", String.class))
            .one()
            .map(encrypted -> decryptSecret(encrypted, requireAppMasterKey()));
    }

    static String encryptSecret(String plaintext, String masterKey) {
        byte[] nonce = new byte[16];
        new SecureRandom().nextBytes(nonce);
        return encryptSecretWithNonce(plaintext, masterKey, nonce);
    }

    static String encryptSecretWithNonce(String plaintext, String masterKey, byte[] nonce) {
        byte[] plaintextBytes = plaintext.getBytes(StandardCharsets.UTF_8);
        byte[] keystream = deriveKeystream(masterKey, nonce, plaintextBytes.length);
        byte[] ciphertext = xor(plaintextBytes, keystream);
        byte[] payload = ByteBuffer.allocate(nonce.length + ciphertext.length)
            .put(nonce)
            .put(ciphertext)
            .array();
        return Base64.getUrlEncoder().encodeToString(payload);
    }

    static String decryptSecret(String ciphertext, String masterKey) {
        byte[] payload = Base64.getUrlDecoder().decode(ciphertext.getBytes(StandardCharsets.UTF_8));
        byte[] nonce = java.util.Arrays.copyOfRange(payload, 0, 16);
        byte[] encryptedBytes = java.util.Arrays.copyOfRange(payload, 16, payload.length);
        byte[] keystream = deriveKeystream(masterKey, nonce, encryptedBytes.length);
        return new String(xor(encryptedBytes, keystream), StandardCharsets.UTF_8);
    }

    private static byte[] deriveKeystream(String masterKey, byte[] nonce, int length) {
        byte[] seed = sha256(concat(masterKey.getBytes(StandardCharsets.UTF_8), nonce));
        ByteBuffer keystream = ByteBuffer.allocate(length);
        int counter = 0;
        while (keystream.position() < length) {
            byte[] block = sha256(concat(seed, ByteBuffer.allocate(4).putInt(counter).array()));
            keystream.put(block, 0, Math.min(block.length, keystream.remaining()));
            counter++;
        }
        return keystream.array();
    }

    private Mono<Void> upsertSetting(String key, String value) {
        DatabaseClient.GenericExecuteSpec spec = databaseClient.sql("""
                INSERT INTO settings (key, value, created_at, updated_at)
                VALUES (:key, :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
                """)
            .bind("key", key);
        spec = bindNullable(spec, "value", value, String.class);
        return spec.fetch().rowsUpdated().then();
    }

    private Mono<Void> upsertSecretSetting(String key, String encryptedValue) {
        return databaseClient.sql("""
                INSERT INTO secret_settings (key, encrypted_value, updated_at)
                VALUES (:key, :encryptedValue, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE
                SET encrypted_value = EXCLUDED.encrypted_value,
                    updated_at = CURRENT_TIMESTAMP
                """)
            .bind("key", key)
            .bind("encryptedValue", encryptedValue)
            .fetch()
            .rowsUpdated()
            .then();
    }

    private SettingsDtos.SettingsResponse toResponse(AppSettings settings) {
        return new SettingsDtos.SettingsResponse(
            settings.dailyDigestTime(),
            settings.weeklyDigestDayOfWeek(),
            settings.weeklyDigestTime(),
            properties.observability().dashboardUrl(),
            settings.recipientEmail(),
            settings.senderIdentity(),
            settings.smtpHost(),
            settings.smtpPort(),
            settings.smtpUsername(),
            settings.smtpSecurityMode(),
            settings.dailyDigestEnabled(),
            settings.dailyDigestCatchUpEnabled(),
            settings.weeklyDigestEnabled(),
            settings.weeklyDigestCatchUpEnabled(),
            settings.smtpPasswordConfigured(),
            settings.analysisSummaryPrompt(),
            settings.analysisVerdictReasonPrompt()
        );
    }

    private String requireAppMasterKey() {
        String appMasterKey = properties.email().appMasterKey();
        if (hasText(appMasterKey)) {
            return appMasterKey;
        }
        throw new IllegalStateException(
            "Missing app master key contract GOOD_NEWS_APP_MASTER_KEY; set it explicitly for SMTP secret encryption."
        );
    }

    private static DatabaseClient.GenericExecuteSpec bindNullable(
        DatabaseClient.GenericExecuteSpec spec,
        String name,
        String value,
        Class<String> type
    ) {
        return value == null ? spec.bindNull(name, type) : spec.bind(name, value);
    }

    private static boolean asBoolean(String value, boolean defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        return "true".equalsIgnoreCase(value);
    }

    private static String blankToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value;
    }

    private static String defaultIfBlank(String value, String defaultValue) {
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        return value;
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private static byte[] concat(byte[] left, byte[] right) {
        ByteBuffer buffer = ByteBuffer.allocate(left.length + right.length);
        return buffer.put(left).put(right).array();
    }

    private static byte[] xor(byte[] left, byte[] right) {
        byte[] result = new byte[left.length];
        for (int index = 0; index < left.length; index++) {
            result[index] = (byte) (left[index] ^ right[index]);
        }
        return result;
    }

    private static byte[] sha256(byte[] value) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(value);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("Missing SHA-256 support", exception);
        }
    }

    public record AppSettings(
        String dailyDigestTime,
        String weeklyDigestDayOfWeek,
        String weeklyDigestTime,
        String recipientEmail,
        String senderIdentity,
        String smtpHost,
        int smtpPort,
        String smtpUsername,
        String smtpSecurityMode,
        boolean dailyDigestEnabled,
        boolean dailyDigestCatchUpEnabled,
        boolean weeklyDigestEnabled,
        boolean weeklyDigestCatchUpEnabled,
        boolean smtpPasswordConfigured,
        String analysisSummaryPrompt,
        String analysisVerdictReasonPrompt
    ) {}

    public record AppSettingsUpdate(
        String dailyDigestTime,
        String weeklyDigestDayOfWeek,
        String weeklyDigestTime,
        String recipientEmail,
        String senderIdentity,
        String smtpHost,
        int smtpPort,
        String smtpUsername,
        String smtpSecurityMode,
        boolean dailyDigestEnabled,
        boolean dailyDigestCatchUpEnabled,
        boolean weeklyDigestEnabled,
        boolean weeklyDigestCatchUpEnabled,
        String smtpPassword,
        String analysisSummaryPrompt,
        String analysisVerdictReasonPrompt
    ) {}

    private record StoredSettingRow(String key, String value) {}
}
