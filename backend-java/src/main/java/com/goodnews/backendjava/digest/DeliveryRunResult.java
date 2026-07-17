package com.goodnews.backendjava.digest;

public record DeliveryRunResult(long digestId, String status, boolean delivered, int itemCount) {}
