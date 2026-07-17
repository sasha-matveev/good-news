package com.goodnews.backendjava.digest;

import java.util.List;

public record GeneratedDigest(
        long digestId, DigestType type, String subject, String htmlBody, List<DigestEmailPost> posts, int moreCount) {

    public int itemCount() {
        return posts.size();
    }
}
