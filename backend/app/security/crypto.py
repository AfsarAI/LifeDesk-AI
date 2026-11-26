"""Symmetric Fernet encryption for OAuth access and refresh tokens at rest."""

from cryptography.fernet import Fernet, InvalidToken


class TokenEncryptionError(Exception):
    """Raised when encryption key configuration is missing/invalid or decryption fails."""


class TokenCipher:
    """Encrypts and decrypts OAuth tokens using a dedicated Fernet key."""

    VERSION = "fernet-v1"

    def __init__(self, key: str | None) -> None:
        if not key:
            raise TokenEncryptionError(
                "TOKEN_ENCRYPTION_KEY is not configured. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except Exception as exc:
            raise TokenEncryptionError(
                "TOKEN_ENCRYPTION_KEY must be a valid 32-byte url-safe base64 Fernet key."
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a secret string into a UTF-8 Fernet token."""
        if not plaintext:
            raise ValueError("Cannot encrypt an empty token.")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a stored Fernet token back into plaintext."""
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise TokenEncryptionError(
                "Stored integration credential could not be decrypted with the current key."
            ) from exc
