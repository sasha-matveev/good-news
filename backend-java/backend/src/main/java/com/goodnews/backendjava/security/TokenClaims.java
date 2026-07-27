package com.goodnews.backendjava.security;

public record TokenClaims(String email, boolean emailVerified) {}
