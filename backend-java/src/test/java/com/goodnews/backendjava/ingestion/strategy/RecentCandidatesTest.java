package com.goodnews.backendjava.ingestion.strategy;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.ListingCandidate;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class RecentCandidatesTest {
    private static final Instant BASE = Instant.parse("2025-06-01T00:00:00Z");

    @Test
    void filtersOldPostsButRetainsUndatedPosts() {
        List<CandidatePost> selected = RecentCandidates.posts(
                List.of(post("old", BASE), post("new", BASE.plus(2, ChronoUnit.DAYS)), post("undated", null)),
                BASE.plus(1, ChronoUnit.DAYS));

        assertThat(selected).extracting(CandidatePost::title).containsExactly("new", "undated");
    }

    @Test
    void selectsNewestTwentyFiveWhilePreservingOriginalOrder() {
        List<CandidatePost> input = new ArrayList<>();
        for (int index = 0; index < 30; index++) {
            input.add(post("post-" + index, BASE.plus(index, ChronoUnit.HOURS)));
        }

        List<CandidatePost> selected = RecentCandidates.posts(input, null);

        assertThat(selected).hasSize(25);
        assertThat(selected.getFirst().title()).isEqualTo("post-5");
        assertThat(selected.getLast().title()).isEqualTo("post-29");
    }

    @Test
    void listingSelectionKeepsPreEnrichedAndUndatedCandidates() {
        ListingCandidate oldEnriched = listing("old-enriched", BASE, "summary");
        ListingCandidate old = listing("old", BASE, null);
        ListingCandidate undated = listing("undated", null, null);

        assertThat(RecentCandidates.listings(List.of(oldEnriched, old, undated), BASE.plusSeconds(1)))
                .extracting(ListingCandidate::title)
                .containsExactly("old-enriched", "undated");
    }

    @Test
    void equalPostsAtCutoffStillReturnExactlyFirstTwentyFiveIndexes() {
        List<CandidatePost> input = new ArrayList<>();
        for (int index = 0; index < 30; index++) {
            input.add(post("equal", BASE));
        }

        List<CandidatePost> selected = RecentCandidates.posts(input, null);

        assertThat(selected).hasSize(25);
        for (int index = 0; index < 25; index++) {
            assertThat(selected.get(index)).isSameAs(input.get(index));
        }
    }

    @Test
    void equalListingsAtCutoffStillReturnExactlyFirstTwentyFiveIndexes() {
        List<ListingCandidate> input = new ArrayList<>();
        for (int index = 0; index < 30; index++) {
            input.add(listing("equal", BASE, null));
        }

        List<ListingCandidate> selected = RecentCandidates.listings(input, null);

        assertThat(selected).hasSize(25);
        for (int index = 0; index < 25; index++) {
            assertThat(selected.get(index)).isSameAs(input.get(index));
        }
    }

    private static CandidatePost post(String title, Instant publishedAt) {
        return new CandidatePost("https://example.com/" + title, title, publishedAt, title, PublicationDateSource.NONE);
    }

    private static ListingCandidate listing(String title, Instant publishedAt, String content) {
        return new ListingCandidate("/" + title, title, publishedAt, PublicationDateSource.NONE, content);
    }
}
