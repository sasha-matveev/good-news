package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.dto.FeedbackDtos;
import com.goodnews.backendjava.service.FeedbackService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Pattern;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@Validated
@RestController
public class FeedbackController {

    private final FeedbackService feedbackService;

    public FeedbackController(FeedbackService feedbackService) {
        this.feedbackService = feedbackService;
    }

    @PutMapping("/api/feedback/{postId}")
    public Mono<FeedbackDtos.FeedbackResponse> updateFeedback(
            @PathVariable long postId, @Valid @RequestBody FeedbackDtos.FeedbackUpdateRequest request) {
        return feedbackService.updateFeedback(postId, request.state());
    }

    @GetMapping("/api/feedback/{postId}/{state}")
    public Mono<ResponseEntity<Void>> saveFeedback(
            @PathVariable long postId,
            @PathVariable
                    @Pattern(
                            regexp = "interesting|not_interesting|want_to_read|norm",
                            message = "state must be one of interesting, not_interesting, want_to_read, norm")
                    String state,
            @RequestParam(name = "digest_id", required = false) String digestId) {
        return feedbackService.saveFeedback(postId, state, digestId);
    }
}
