package com.goodnews.backendjava.ingestion.infrastructure.http;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import java.net.InetAddress;
import java.net.URI;
import java.net.UnknownHostException;
import java.util.Arrays;
import java.util.List;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Component
public class PublicSourceUrlPolicy {
    private static final List<Cidr> IPV4_SPECIAL = cidrs(
            "0.0.0.0/8",
            "10.0.0.0/8",
            "100.64.0.0/10",
            "127.0.0.0/8",
            "169.254.0.0/16",
            "172.16.0.0/12",
            "192.0.0.0/24",
            "192.0.2.0/24",
            "192.168.0.0/16",
            "198.18.0.0/15",
            "198.51.100.0/24",
            "203.0.113.0/24",
            "224.0.0.0/4",
            "240.0.0.0/4");
    private static final List<Cidr> IPV6_SPECIAL = cidrs(
            "::/128",
            "::1/128",
            "64:ff9b:1::/48",
            "100::/64",
            "2001:10::/28",
            "2001:db8::/32",
            "fc00::/7",
            "fe80::/10",
            "ff00::/8");

    public Mono<ValidatedUrl> validate(String rawUrl) {
        URI uri;
        try {
            uri = URI.create(rawUrl);
        } catch (IllegalArgumentException error) {
            return Mono.error(new SourceIngestionException("Invalid source URL", error));
        }
        if (!("http".equalsIgnoreCase(uri.getScheme()) || "https".equalsIgnoreCase(uri.getScheme()))
                || uri.getHost() == null) {
            return Mono.error(new SourceIngestionException("Source URL must use HTTP or HTTPS"));
        }
        URI candidate = uri;
        return Mono.fromCallable(() -> {
                    InetAddress[] addresses = InetAddress.getAllByName(candidate.getHost());
                    if (addresses.length == 0 || Arrays.stream(addresses).anyMatch(PublicSourceUrlPolicy::nonPublic)) {
                        throw new SourceIngestionException("Source URL does not resolve to a public destination");
                    }
                    return new ValidatedUrl(candidate, List.of(addresses));
                })
                .subscribeOn(Schedulers.boundedElastic())
                .onErrorMap(
                        UnknownHostException.class,
                        error -> new SourceIngestionException("Source host cannot be resolved", error));
    }

    private static boolean nonPublic(InetAddress address) {
        if (address.isAnyLocalAddress()
                || address.isLoopbackAddress()
                || address.isLinkLocalAddress()
                || address.isSiteLocalAddress()
                || address.isMulticastAddress()) {
            return true;
        }
        List<Cidr> ranges = address.getAddress().length == 4 ? IPV4_SPECIAL : IPV6_SPECIAL;
        return ranges.stream().anyMatch(range -> range.contains(address));
    }

    private static List<Cidr> cidrs(String... values) {
        return Arrays.stream(values).map(Cidr::parse).toList();
    }

    public record ValidatedUrl(URI uri, List<InetAddress> addresses) {}

    private record Cidr(byte[] network, int prefixLength) {
        static Cidr parse(String value) {
            String[] parts = value.split("/");
            try {
                return new Cidr(InetAddress.getByName(parts[0]).getAddress(), Integer.parseInt(parts[1]));
            } catch (UnknownHostException error) {
                throw new IllegalStateException(error);
            }
        }

        boolean contains(InetAddress address) {
            byte[] candidate = address.getAddress();
            if (candidate.length != network.length) {
                return false;
            }
            int complete = prefixLength / 8;
            int remaining = prefixLength % 8;
            for (int index = 0; index < complete; index++) {
                if (candidate[index] != network[index]) {
                    return false;
                }
            }
            if (remaining == 0) {
                return true;
            }
            int mask = 0xff << (8 - remaining);
            return (candidate[complete] & mask) == (network[complete] & mask);
        }
    }
}
