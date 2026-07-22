package com.goodnews.backendjava.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.goodnews.backendjava.config.EmailProperties;
import com.goodnews.backendjava.config.GoodNewsProperties;
import java.time.Duration;
import java.util.Properties;
import org.junit.jupiter.api.Test;

class JakartaMailSmtpEmailAdapterTest {

    @Test
    void appliesBoundedSmtpConnectionReadAndWriteTimeouts() {
        GoodNewsProperties goodNews = mock(GoodNewsProperties.class);
        when(goodNews.email())
                .thenReturn(new EmailProperties(
                        null, null, null, Duration.ofSeconds(4), Duration.ofSeconds(14), Duration.ofSeconds(15)));
        JakartaMailSmtpEmailAdapter adapter = new JakartaMailSmtpEmailAdapter(goodNews);

        Properties mail = adapter.mailProperties(
                new SmtpEmailAdapter.SmtpConnectionSettings("smtp.example", 587, "user", "secret", "starttls"));

        assertThat(mail.getProperty("mail.smtp.connectiontimeout")).isEqualTo("4000");
        assertThat(mail.getProperty("mail.smtp.timeout")).isEqualTo("14000");
        assertThat(mail.getProperty("mail.smtp.writetimeout")).isEqualTo("15000");
    }
}
