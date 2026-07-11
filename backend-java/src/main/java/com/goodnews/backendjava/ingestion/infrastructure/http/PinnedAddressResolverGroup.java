package com.goodnews.backendjava.ingestion.infrastructure.http;

import io.netty.resolver.AbstractAddressResolver;
import io.netty.resolver.AddressResolver;
import io.netty.resolver.AddressResolverGroup;
import io.netty.util.concurrent.EventExecutor;
import io.netty.util.concurrent.Promise;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.List;

final class PinnedAddressResolverGroup extends AddressResolverGroup<InetSocketAddress> {
    private final List<InetAddress> addresses;

    PinnedAddressResolverGroup(List<InetAddress> addresses) {
        this.addresses = List.copyOf(addresses);
    }

    @Override
    protected AddressResolver<InetSocketAddress> newResolver(EventExecutor executor) {
        return new AbstractAddressResolver<>(executor) {
            @Override
            protected boolean doIsResolved(InetSocketAddress address) {
                return false;
            }

            @Override
            protected void doResolve(InetSocketAddress unresolved, Promise<InetSocketAddress> promise) {
                promise.setSuccess(new InetSocketAddress(addresses.getFirst(), unresolved.getPort()));
            }

            @Override
            protected void doResolveAll(InetSocketAddress unresolved, Promise<List<InetSocketAddress>> promise) {
                promise.setSuccess(addresses.stream()
                        .map(address -> new InetSocketAddress(address, unresolved.getPort()))
                        .toList());
            }
        };
    }
}
