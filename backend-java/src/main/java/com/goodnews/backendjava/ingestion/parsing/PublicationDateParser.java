package com.goodnews.backendjava.ingestion.parsing;

import java.time.Instant;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.Locale;
import org.springframework.stereotype.Component;

@Component
public final class PublicationDateParser {
    public Instant parse(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String raw = value.trim();
        for (DateParser parser : List.<DateParser>of(this::instant, this::offset, this::rfc1123, this::localDate)) {
            Instant parsed = parser.parse(raw);
            if (parsed != null) {
                return parsed;
            }
        }
        for (String pattern : List.of("MMMM d, uuuu", "MMM d, uuuu", "MMM. d, uuuu")) {
            try {
                return LocalDate.parse(raw, DateTimeFormatter.ofPattern(pattern, Locale.ENGLISH))
                        .atStartOfDay()
                        .toInstant(ZoneOffset.UTC);
            } catch (DateTimeParseException ignored) {
                // Try the next supported representation.
            }
        }
        return null;
    }

    private Instant instant(String value) {
        try {
            return Instant.parse(value);
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    private Instant offset(String value) {
        try {
            return OffsetDateTime.parse(value).toInstant();
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    private Instant rfc1123(String value) {
        try {
            return ZonedDateTime.parse(value, DateTimeFormatter.RFC_1123_DATE_TIME)
                    .toInstant();
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    private Instant localDate(String value) {
        try {
            return LocalDate.parse(value).atStartOfDay().toInstant(ZoneOffset.UTC);
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    @FunctionalInterface
    private interface DateParser {
        Instant parse(String value);
    }
}
