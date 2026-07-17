package com.goodnews.backendjava.digest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import org.junit.jupiter.api.Test;

class DigestEmailRendererTest {

    private final DigestEmailRenderer renderer = new DigestEmailRenderer();

    @Test
    void rendersStableEscapedHtmlWithFeedbackLinksAndRemainder() {
        DigestEmailPost post = new DigestEmailPost(
                42,
                "Java <Reactor>",
                null,
                "https://post.example/read?a=1&b=2",
                "Кратко & ясно",
                "interesting",
                "Useful <today>",
                9);

        String html = renderer.render("Good News & Java", List.of(post), 2, "https://api.example/api/feedback///", 7);

        assertThat(html)
                .isEqualTo("<html><body><h1>Good News &amp; Java</h1>"
                        + "<article><h2>Java &lt;Reactor&gt;</h2>"
                        + "<p>Source: Unknown</p><p>Match: 9/10</p>"
                        + "<p><a href=\"https://post.example/read?a=1&amp;b=2\">Open original</a></p>"
                        + "<p>Кратко &amp; ясно</p><p>Verdict: interesting</p>"
                        + "<p>Reason: Useful &lt;today&gt;</p>"
                        + "<p><a href=\"https://api.example/api/feedback/42/interesting?digest_id=7\">interesting</a></p>"
                        + "<p><a href=\"https://api.example/api/feedback/42/not_interesting?digest_id=7\">not_interesting</a></p>"
                        + "<p><a href=\"https://api.example/api/feedback/42/want_to_read?digest_id=7\">want_to_read</a></p>"
                        + "</article><p>...and 2 more posts in the collection.</p></body></html>");
    }

    @Test
    void omitsOptionalMatchAndRemainder() {
        DigestEmailPost post = new DigestEmailPost(1, "Title", "Source", "https://post", null, null, null, null);

        String html = renderer.render("Digest", List.of(post), 0, "https://api/feedback", 3);

        assertThat(html).doesNotContain("Match:", "...and").contains("<p></p>", "<p>Verdict: </p>");
    }

    @Test
    void omitsOriginalLinkForUnsafeOrMalformedSchemes() {
        List<DigestEmailPost> posts = List.of(
                new DigestEmailPost(1, "Script", "Source", "javascript:alert(1)", null, null, null, null),
                new DigestEmailPost(2, "Data", "Source", "data:text/html,bad", null, null, null, null),
                new DigestEmailPost(3, "Broken", "Source", "https://bad host", null, null, null, null));

        String html = renderer.render("Digest", posts, 0, "https://api/feedback", 3);

        assertThat(html)
                .doesNotContain("javascript:", "data:text", "https://bad host")
                .doesNotContain("Open original");
    }

    @Test
    void rejectsUnsafeFeedbackBaseUrl() {
        assertThatThrownBy(() -> renderer.render("Digest", List.of(), 0, "javascript:alert(1)", 3))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Feedback base URL must be an absolute HTTP(S) URL");
    }
}
