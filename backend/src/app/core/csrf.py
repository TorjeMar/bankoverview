import hashlib
import hmac

from app.core.config import settings


def generate_csrf_token(session_id: str) -> str:
    return hmac.new(
        settings.csrf_secret.encode(), session_id.encode(), hashlib.sha256
    ).hexdigest()
