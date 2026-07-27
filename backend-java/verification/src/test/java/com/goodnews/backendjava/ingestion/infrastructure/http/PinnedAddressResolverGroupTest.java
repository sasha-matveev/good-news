package com.goodnews.backendjava.ingestion.infrastructure.http;

import static org.assertj.core.api.Assertions.assertThat;

import io.netty.channel.DefaultEventLoop;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.List;
import org.junit.jupiter.api.Test;

class PinnedAddressResolverGroupTest {
    @Test
    void resolvesUnresolvableHostnameOnlyToPinnedAddressesAndPreservesPort() throws Exception {
        InetAddress first = InetAddress.getByAddress(new byte[] {(byte) 203, 0, 113, 10});
        InetAddress second = InetAddress.getByAddress(new byte[] {(byte) 198, 51, 100, 20});
        PinnedAddressResolverGroup group = new PinnedAddressResolverGroup(List.of(first, second));
        DefaultEventLoop eventLoop = new DefaultEventLoop();
        try {
            var resolver = group.getResolver(eventLoop);
            InetSocketAddress unresolved = InetSocketAddress.createUnresolved("cannot-resolve.invalid", 8443);

            assertThat(resolver.resolve(unresolved).syncUninterruptibly().getNow())
                    .extracting(InetSocketAddress::getAddress, InetSocketAddress::getPort)
                    .containsExactly(first, 8443);
            assertThat(resolver.resolveAll(unresolved).syncUninterruptibly().getNow())
                    .extracting(InetSocketAddress::getAddress)
                    .containsExactly(first, second);
            assertThat(resolver.resolveAll(unresolved).syncUninterruptibly().getNow())
                    .extracting(InetSocketAddress::getPort)
                    .containsOnly(8443);
        } finally {
            group.close();
            eventLoop.shutdownGracefully().syncUninterruptibly();
        }
    }
}
