package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.dto.SourceDtos;
import com.goodnews.backendjava.service.SourceManagementService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
public class SourcesController {
    private final SourceManagementService service;

    public SourcesController(SourceManagementService service) {
        this.service = service;
    }

    @GetMapping("/api/sources")
    public Flux<SourceDtos.SourceResponse> list() {
        return service.list();
    }

    @GetMapping("/api/sources/{id}/log")
    public Mono<SourceDtos.SourceLogResponse> log(@PathVariable long id) {
        return service.log(id);
    }

    @PostMapping("/api/sources")
    @ResponseStatus(HttpStatus.CREATED)
    public Mono<SourceDtos.SourceResponse> create(@Valid @RequestBody SourceDtos.SourceCreateRequest body) {
        return service.create(body.url());
    }

    @PatchMapping("/api/sources/{id}")
    public Mono<SourceDtos.SourceResponse> update(
            @PathVariable long id, @Valid @RequestBody SourceDtos.SourceUpdateRequest body) {
        return service.update(id, body.active());
    }

    @DeleteMapping("/api/sources/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public Mono<Void> delete(@PathVariable long id) {
        return service.delete(id);
    }
}
