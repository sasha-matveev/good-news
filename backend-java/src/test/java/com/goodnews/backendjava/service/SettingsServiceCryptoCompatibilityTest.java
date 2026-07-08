package com.goodnews.backendjava.service;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SettingsServiceCryptoCompatibilityTest {

    @Test
    void decryptsPythonCompatibleCiphertextVector() {
        assertThat(
            SettingsService.decryptSecret(
                "ABEiM0RVZneImaq7zN3u_21dRzgKx2qy8JevEwLIIFUD",
                "test-master-key"
            )
        ).isEqualTo("smtp-password-123");

        assertThat(
            SettingsService.decryptSecret(
                "_ty6mHZUMhABI0VniavN7zIGQz9ZYjfxOCYxHg==",
                "master-key-2"
            )
        ).isEqualTo("пароль");
    }

    @Test
    void encryptsPythonCompatibleCiphertextVectorWhenNonceIsFixed() {
        byte[] nonce = new byte[] {
            0x00, 0x11, 0x22, 0x33,
            0x44, 0x55, 0x66, 0x77,
            (byte) 0x88, (byte) 0x99, (byte) 0xaa, (byte) 0xbb,
            (byte) 0xcc, (byte) 0xdd, (byte) 0xee, (byte) 0xff
        };

        assertThat(SettingsService.encryptSecretWithNonce("smtp-password-123", "test-master-key", nonce))
            .isEqualTo("ABEiM0RVZneImaq7zN3u_21dRzgKx2qy8JevEwLIIFUD");
    }
}
