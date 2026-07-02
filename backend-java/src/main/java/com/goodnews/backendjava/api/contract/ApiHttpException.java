package com.goodnews.backendjava.api.contract;

import org.springframework.http.HttpStatus;

public class ApiHttpException extends RuntimeException {

    private final HttpStatus status;

    public ApiHttpException(HttpStatus status, String detail) {
        super(detail);
        this.status = status;
    }

    public HttpStatus getStatus() {
        return status;
    }
}
