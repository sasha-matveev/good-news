package com.goodnews.backendjava.api.contract;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.springframework.core.MethodParameter;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.bind.support.WebExchangeBindException;
import org.springframework.web.method.annotation.HandlerMethodValidationException;

@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class ApiErrorHandler {

    @ExceptionHandler(ApiHttpException.class)
    public ResponseEntity<Map<String, Object>> handleApiHttpException(ApiHttpException exception) {
        return ResponseEntity.status(exception.getStatus()).body(Map.of("detail", exception.getMessage()));
    }

    @ExceptionHandler(WebExchangeBindException.class)
    public ResponseEntity<Map<String, Object>> handleBindException(WebExchangeBindException exception) {
        List<ValidationErrorItem> detail =
                exception.getFieldErrors().stream().map(this::fromFieldError).toList();
        return ResponseEntity.unprocessableEntity().body(Map.of("detail", detail));
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    public ResponseEntity<Map<String, Object>> handleMethodValidationException(
            HandlerMethodValidationException exception) {
        List<ValidationErrorItem> detail = exception.getAllValidationResults().stream()
                .flatMap(result -> result.getResolvableErrors().stream().map(error -> {
                    String fieldName = result.getMethodParameter().getParameterName();
                    return new ValidationErrorItem(
                            List.of(resolveLocation(result.getMethodParameter()), fieldName),
                            Objects.requireNonNullElse(error.getDefaultMessage(), "Validation failed"),
                            "value_error");
                }))
                .toList();
        return ResponseEntity.unprocessableEntity().body(Map.of("detail", detail));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArgumentException(IllegalArgumentException exception) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("detail", exception.getMessage()));
    }

    private ValidationErrorItem fromFieldError(FieldError error) {
        return new ValidationErrorItem(
                List.of("body", error.getField()),
                Objects.requireNonNullElse(error.getDefaultMessage(), "Validation failed"),
                "value_error");
    }

    private String resolveLocation(MethodParameter parameter) {
        if (parameter.hasParameterAnnotation(RequestBody.class)) {
            return "body";
        }
        if (parameter.hasParameterAnnotation(PathVariable.class)) {
            return "path";
        }
        if (parameter.hasParameterAnnotation(RequestHeader.class)) {
            return "header";
        }
        if (parameter.hasParameterAnnotation(CookieValue.class)) {
            return "cookie";
        }
        if (parameter.hasParameterAnnotation(RequestParam.class)) {
            return "query";
        }
        return "query";
    }

    record ValidationErrorItem(List<String> loc, String msg, String type) {}
}
