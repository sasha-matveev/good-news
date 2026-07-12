package com.goodnews.backendjava.service;

import com.goodnews.backendjava.api.dto.WantToReadDtos;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import reactor.core.publisher.Mono;

@Service
public class WantToReadService {

    private final PostService postService;
    private final FeedbackService feedbackService;

    public WantToReadService(PostService postService, FeedbackService feedbackService) {
        this.postService = postService;
        this.feedbackService = feedbackService;
    }

    @Transactional
    public Mono<WantToReadDtos.WantToReadUpdateResponse> updateWantToRead(long postId, boolean saved) {
        return postService
                .requirePostExists(postId)
                .then(
                        saved
                                ? feedbackService
                                        .updateFeedback(postId, "want_to_read")
                                        .map(response -> new WantToReadDtos.WantToReadUpdateResponse(
                                                postId, true, response.state()))
                                : feedbackService
                                        .currentFeedbackState(postId)
                                        .flatMap(currentState -> {
                                            if ("want_to_read".equals(currentState)) {
                                                return feedbackService
                                                        .deleteFeedback(postId)
                                                        .thenReturn(new WantToReadDtos.WantToReadUpdateResponse(
                                                                postId, false, null));
                                            }
                                            return Mono.just(new WantToReadDtos.WantToReadUpdateResponse(
                                                    postId, false, currentState));
                                        })
                                        .switchIfEmpty(Mono.just(
                                                new WantToReadDtos.WantToReadUpdateResponse(postId, false, null))));
    }
}
