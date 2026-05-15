from __future__ import annotations

import ctypes
import os
import sys

APP_MASTER_KEY_SECRET_NAME = "good-news/dev/app-master-key"
POSTGRES_PASSWORD_SECRET_NAME = "good-news/dev/postgres-password"
_CRED_TYPE_GENERIC = 1
_ERROR_NOT_FOUND = 1168


class SecretStoreError(RuntimeError):
    """Base error for secret store access problems."""


class SecretNotFoundError(SecretStoreError):
    """Raised when a required secret does not exist."""


class SecretStore:
    def get_secret(self, name: str) -> str:
        raise NotImplementedError

    def has_secret(self, name: str) -> bool:
        try:
            self.get_secret(name)
        except SecretNotFoundError:
            return False
        return True


class InMemorySecretStore(SecretStore):
    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = dict(secrets or {})

    def get_secret(self, name: str) -> str:
        try:
            return self._secrets[name]
        except KeyError as exc:
            raise SecretNotFoundError(f"Secret not found: {name}") from exc

    def set_secret(self, name: str, value: str) -> None:
        self._secrets[name] = value


if sys.platform == "win32":
    from ctypes import wintypes

    class _Credential(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    class WindowsCredentialManagerSecretStore(SecretStore):
        @staticmethod
        def _read_secret_bytes(name: str) -> bytes:
            cred_ptr = ctypes.POINTER(_Credential)()
            advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
            cred_read = advapi32.CredReadW
            cred_read.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.POINTER(_Credential)),
            ]
            cred_read.restype = wintypes.BOOL
            cred_free = advapi32.CredFree
            cred_free.argtypes = [ctypes.c_void_p]
            cred_free.restype = None

            if not cred_read(name, _CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr)):
                error_code = ctypes.get_last_error()
                if error_code == _ERROR_NOT_FOUND:
                    raise SecretNotFoundError(f"Secret not found: {name}")
                raise SecretStoreError(f"Credential Manager read failed for {name}: {error_code}")

            try:
                credential = cred_ptr.contents
                return ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            finally:
                cred_free(cred_ptr)

        def get_secret(self, name: str) -> str:
            return self._read_secret_bytes(name).decode("utf-16-le")

else:
    class WindowsCredentialManagerSecretStore(SecretStore):  # type: ignore[no-redef]
        """Stub on non-Windows platforms. create_platform_secret_store() returns None here."""

        def get_secret(self, name: str) -> str:
            raise NotImplementedError("Windows Credential Manager is not available on this platform")


class EnvironmentVariableSecretStore(SecretStore):
    """Reads secrets from environment variables. Suitable for cloud and CI environments."""

    _ENV_VAR_BY_SECRET_NAME: dict[str, str] = {
        APP_MASTER_KEY_SECRET_NAME: "GOOD_NEWS_APP_MASTER_KEY",
        POSTGRES_PASSWORD_SECRET_NAME: "GOOD_NEWS_POSTGRES_PASSWORD",
    }

    def get_secret(self, name: str) -> str:
        env_var = self._ENV_VAR_BY_SECRET_NAME.get(name)
        if env_var:
            value = os.getenv(env_var)
            if value is not None and value != "":
                return value
            if value == "":
                raise SecretNotFoundError(
                    f"Secret env var '{env_var}' is set but empty; set it to a non-empty value or unset it"
                )
        raise SecretNotFoundError(f"Secret not found in environment: {name}")


def create_platform_secret_store() -> SecretStore | None:
    """Returns a platform-appropriate secret store.

    On Windows: WindowsCredentialManagerSecretStore (fallback after env vars).
    On other platforms: None (rely on env vars via Settings._resolve_secret).
    """
    if sys.platform == "win32":
        return WindowsCredentialManagerSecretStore()
    return None
