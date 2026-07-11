package com.goodnews.backendjava.ingestion.strategy;

import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.ListingCandidate;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.IntStream;

final class RecentCandidates {
    private static final int LIMIT = 25;

    private RecentCandidates() {}

    static List<CandidatePost> posts(List<CandidatePost> posts, Instant lastSuccess) {
        List<CandidatePost> selected = lastSuccess == null
                ? posts
                : posts.stream()
                        .filter(post ->
                                post.publishedAt() == null || post.publishedAt().isAfter(lastSuccess))
                        .toList();
        if (selected.size() <= LIMIT) {
            return selected;
        }
        return newestInOriginalOrder(selected, CandidatePost::publishedAt);
    }

    static List<ListingCandidate> listings(List<ListingCandidate> items, Instant lastSuccess) {
        List<ListingCandidate> selected = lastSuccess == null
                ? items
                : items.stream()
                        .filter(item -> item.rawContent() != null
                                || item.publishedAt() == null
                                || item.publishedAt().isAfter(lastSuccess))
                        .toList();
        if (selected.size() <= LIMIT) {
            return selected;
        }
        return newestInOriginalOrder(selected, ListingCandidate::publishedAt);
    }

    private static <T> List<T> newestInOriginalOrder(List<T> candidates, Function<T, Instant> publishedAt) {
        Set<Integer> selectedIndexes = IntStream.range(0, candidates.size())
                .boxed()
                .sorted(Comparator.comparing((Integer index) -> instant(publishedAt.apply(candidates.get(index))))
                        .reversed()
                        .thenComparingInt(Integer::intValue))
                .limit(LIMIT)
                .collect(java.util.stream.Collectors.toSet());
        return IntStream.range(0, candidates.size())
                .filter(selectedIndexes::contains)
                .mapToObj(candidates::get)
                .toList();
    }

    private static Instant instant(Instant value) {
        return value == null ? Instant.MIN : value;
    }
}
