package com.goodnews.backendjava.digest;

import java.util.List;
import org.springframework.stereotype.Component;
import org.springframework.web.util.HtmlUtils;

@Component
public final class DigestEmailRenderer {

    public String render(
            String digestTitle, List<DigestEmailPost> posts, int moreCount, String feedbackBaseUrl, long digestId) {
        String normalizedFeedbackBaseUrl = stripTrailingSlashes(feedbackBaseUrl);
        if (!WebUrlPolicy.isSafeAbsoluteWebUrl(normalizedFeedbackBaseUrl)) {
            throw new IllegalArgumentException("Feedback base URL must be an absolute HTTP(S) URL");
        }
        StringBuilder html =
                new StringBuilder("<html><body><h1>").append(text(digestTitle)).append("</h1>");
        for (DigestEmailPost post : posts) {
            html.append("<article><h2>")
                    .append(text(post.title()))
                    .append("</h2>")
                    .append("<p>Source: ")
                    .append(text(post.sourceName() == null ? "Unknown" : post.sourceName()))
                    .append("</p>");
            if (post.relevanceScore() != null) {
                html.append("<p>Match: ").append(post.relevanceScore()).append("/10</p>");
            }
            if (WebUrlPolicy.isSafeAbsoluteWebUrl(post.canonicalUrl())) {
                html.append("<p><a href=\"")
                        .append(attribute(post.canonicalUrl()))
                        .append("\">Open original</a></p>");
            }
            html.append("<p>")
                    .append(text(post.summaryRu()))
                    .append("</p><p>Verdict: ")
                    .append(text(post.verdict()))
                    .append("</p><p>Reason: ")
                    .append(text(post.verdictReason()))
                    .append("</p>");
            appendFeedbackLink(html, normalizedFeedbackBaseUrl, post.postId(), "interesting", digestId);
            appendFeedbackLink(html, normalizedFeedbackBaseUrl, post.postId(), "not_interesting", digestId);
            appendFeedbackLink(html, normalizedFeedbackBaseUrl, post.postId(), "want_to_read", digestId);
            html.append("</article>");
        }
        if (moreCount > 0) {
            html.append("<p>...and ")
                    .append(moreCount)
                    .append(" more post")
                    .append(moreCount == 1 ? "" : "s")
                    .append(" in the collection.</p>");
        }
        return html.append("</body></html>").toString();
    }

    private void appendFeedbackLink(StringBuilder html, String baseUrl, long postId, String state, long digestId) {
        html.append("<p><a href=\"")
                .append(attribute(baseUrl))
                .append('/')
                .append(postId)
                .append('/')
                .append(state)
                .append("?digest_id=")
                .append(digestId)
                .append("\">")
                .append(state)
                .append("</a></p>");
    }

    private String text(String value) {
        return HtmlUtils.htmlEscape(value == null ? "" : value);
    }

    private String attribute(String value) {
        return HtmlUtils.htmlEscape(value == null ? "" : value);
    }

    private String stripTrailingSlashes(String value) {
        int end = value.length();
        while (end > 0 && value.charAt(end - 1) == '/') {
            end--;
        }
        return value.substring(0, end);
    }
}
