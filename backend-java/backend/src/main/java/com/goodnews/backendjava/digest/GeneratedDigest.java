package com.goodnews.backendjava.digest;

import java.util.List;

public record GeneratedDigest(
        long digestId,
        DigestType type,
        String subject,
        String htmlBody,
        List<DigestEmailPost> posts,
        int moreCount,
        int itemCount) {

    public GeneratedDigest(
            long digestId,
            DigestType type,
            String subject,
            String htmlBody,
            List<DigestEmailPost> posts,
            int moreCount) {
        this(digestId, type, subject, htmlBody, posts, moreCount, posts.size());
    }
}
