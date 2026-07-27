package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.dto.WantToReadDtos;
import com.goodnews.backendjava.service.WantToReadService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@RestController
public class WantToReadController {

    private final WantToReadService wantToReadService;

    public WantToReadController(WantToReadService wantToReadService) {
        this.wantToReadService = wantToReadService;
    }

    @PutMapping("/api/want-to-read/{postId}")
    public Mono<WantToReadDtos.WantToReadUpdateResponse> updateWantToRead(
            @PathVariable long postId, @Valid @RequestBody WantToReadDtos.WantToReadUpdateRequest request) {
        return wantToReadService.updateWantToRead(postId, request.saved());
    }
}
