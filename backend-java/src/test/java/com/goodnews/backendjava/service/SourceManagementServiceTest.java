package com.goodnews.backendjava.service;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class SourceManagementServiceTest {
    @ParameterizedTest(name = "{0} normalizes to {1}")
    @CsvSource(
            delimiter = '|',
            textBlock =
                    """
        example.com | https://example.com
         example.com/path/  | https://example.com/path
        http://example.com/path/?query=yes#fragment | http://example.com/path
        https://example.com/path;session=1?query=yes | https://example.com/path
        not a url | https://not a url
        ftp://example.com/feed/ | ftp://example.com/feed
        https://example.com;port | https://example.com;port
        """)
    void matchesPythonSourceUrlNormalization(String input, String expected) {
        assertThat(SourceManagementService.normalize(input)).isEqualTo(expected);
    }
}
