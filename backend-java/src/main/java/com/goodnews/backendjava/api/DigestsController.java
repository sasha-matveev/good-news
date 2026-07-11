package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.dto.DigestDtos;
import com.goodnews.backendjava.service.DigestHistoryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
public class DigestsController {
    private final DigestHistoryService service;
    public DigestsController(DigestHistoryService service) { this.service = service; }
    @GetMapping("/api/digests")
    public Flux<DigestDtos.DigestListItemResponse> list() { return service.listSentDigests(); }
    @GetMapping("/api/digests/{digestId}")
    public Mono<DigestDtos.DigestDetailResponse> detail(@PathVariable long digestId) { return service.getSentDigest(digestId); }
}
