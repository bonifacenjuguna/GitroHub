import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import secrets


def _get_key() -> bytes:
    hex_key = os.environ["AES_ENCRYPTION_KEY"]
    return bytes.fromhex(hex_key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string using AES-256-GCM. Returns base64 encoded ciphertext."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    # Prepend nonce to ciphertext, encode as base64
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt(encrypted: str) -> str:
    """Decrypt a base64 encoded AES-256-GCM ciphertext."""
    key = _get_key()
    aesgcm = AESGCM(key)
    data = base64.b64decode(encrypted.encode())
    nonce = data[:12]
    ciphertext = data[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()
