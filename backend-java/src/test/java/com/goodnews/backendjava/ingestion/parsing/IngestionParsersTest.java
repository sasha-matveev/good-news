package com.goodnews.backendjava.ingestion.parsing;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.knownsite.AnthropicEngineeringParser;
import com.goodnews.backendjava.ingestion.knownsite.ClaudeBlogParser;
import com.goodnews.backendjava.ingestion.knownsite.UberEngineeringParser;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class IngestionParsersTest {
    private final PublicationDateParser dates = new PublicationDateParser();

    @Test
    void parsesFeedAndRemovesBoilerplate() {
        String xml =
                """
                <rss><channel><item><title>Good &amp; Better</title><link>https://example.com/one</link>
                <description>Useful news. The post Good appeared first on Example.</description>
                <pubDate>Tue, 03 Jun 2025 10:00:00 GMT</pubDate></item></channel></rss>
                """;
        var post = new FeedDocumentParser(dates).parse(xml).getFirst();
        assertThat(post.title()).isEqualTo("Good & Better");
        assertThat(post.rawContent()).isEqualTo("Useful news.");
        assertThat(post.publicationDateSource()).isEqualTo(PublicationDateSource.FEED);
    }

    @Test
    void parsesEachKnownSiteWithoutCrossSiteLinks() {
        String cards =
                """
                <article><a href='/blog/good'><h2>Claude</h2></a><time>June 3, 2025</time></article>
                <article><a href='https://evil.example/blog/bad'><h2>Bad</h2></a></article>
                """;
        assertThat(new ClaudeBlogParser(dates).parseListing(cards)).hasSize(1);
        assertThat(new AnthropicEngineeringParser(dates)
                        .parseListing("<article><a href='/engineering/good'><h2>Anthropic</h2></a></article>"))
                .hasSize(1);
        assertThat(new UberEngineeringParser(dates)
                        .parseListing("<a class='blog-card' href='/good'><h3 class='blog-card-title'>Uber</h3></a>"))
                .hasSize(1);
    }

    @Test
    void extractsArticleContentAndJsonLdDate() {
        String html =
                """
                <script type='application/ld+json'>{"datePublished":"2025-06-03T10:00:00Z"}</script>
                <p>Article body</p>
                """;
        var article = new ArticleContentParser(new ObjectMapper(), dates).parse(html, "fallback");
        assertThat(article.rawContent()).isEqualTo("Article body");
        assertThat(article.publicationDateSource()).isEqualTo(PublicationDateSource.JSON_LD);
    }

    @Test
    void malformedKnownSiteHrefIsAnExpectedIngestionFailureWithCause() {
        assertThatThrownBy(() -> new ClaudeBlogParser(dates)
                        .parseListing("<article><a href='/blog/%zz'><h2>Broken</h2></a></article>"))
                .isInstanceOf(SourceIngestionException.class)
                .hasMessageContaining("invalid article URL")
                .hasCauseInstanceOf(IllegalArgumentException.class);
    }
}
