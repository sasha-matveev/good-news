package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.dto.PostDtos;
import com.goodnews.backendjava.service.PostService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@Validated
@RestController
public class PostsController {

    private final PostService postService;

    public PostsController(PostService postService) {
        this.postService = postService;
    }

    @GetMapping("/api/posts")
    public Mono<java.util.List<PostDtos.PostResponse>> listPosts(
        @RequestParam(name = "source_id", required = false) Long sourceId,
        @RequestParam(name = "feedback_state", required = false) String feedbackState,
        @RequestParam(name = "window", defaultValue = "last_month") String window,
        @RequestParam(name = "sort", defaultValue = "match")
        @Pattern(regexp = "match|date", message = "sort must be one of match, date") String sort,
        @RequestParam(name = "limit", required = false) @Min(1) @Max(200) Integer limit,
        @RequestParam(name = "offset", defaultValue = "0") @Min(0) int offset,
        @RequestParam(name = "read_later", required = false) Boolean readLater
    ) {
        return postService.listPosts(sourceId, feedbackState, window, sort, limit, offset, readLater);
    }

    @PostMapping("/api/posts/{postId}/read-later")
    public Mono<PostDtos.ReadLaterResponse> updateReadLater(
        @PathVariable long postId,
        @Valid @RequestBody PostDtos.ReadLaterRequest request
    ) {
        return postService.updateReadLater(postId, request.saved());
    }

    @PostMapping("/api/posts/{postId}/open")
    public Mono<PostDtos.OpenResponse> trackOpen(@PathVariable long postId) {
        return postService.trackOpen(postId);
    }
}
