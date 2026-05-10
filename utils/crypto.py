"""AES-256-GCM encryption for GitHub tokens."""
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from config import settings


def _key() -> bytes:
    return bytes.fromhex(settings.aes_key)


def encrypt(plaintext: str) -> str:
    aesgcm = AESGCM(_key())
    nonce = secrets.token_bytes(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(encrypted: str) -> str:
    aesgcm = AESGCM(_key())
    data = base64.b64decode(encrypted.encode())
    nonce, ct = data[:12], data[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()
