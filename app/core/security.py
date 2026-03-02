import hashlib
import hmac
import secrets


def hash_api_key(api_key: str) -> str:
    """SHA-256 hash of an API key for safe storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return secrets.token_urlsafe(32)


def verify_api_key(plain: str, hashed: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(hash_api_key(plain), hashed)
