package dev.launchpad;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

public class ApiException extends RuntimeException {
    final HttpStatus status;
    public ApiException(HttpStatus status, String detail) { super(detail); this.status = status; }
    static ApiException conflict(String detail) { return new ApiException(HttpStatus.CONFLICT, detail); }
    static ApiException missing() { return new ApiException(HttpStatus.NOT_FOUND, "Resource not found"); }
}

@RestControllerAdvice
class ApiErrors {
    @ExceptionHandler(ApiException.class)
    ProblemDetail handle(ApiException ex) { return ProblemDetail.forStatusAndDetail(ex.status, ex.getMessage()); }
}
