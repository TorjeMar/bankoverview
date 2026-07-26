from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt as pyjwt
import requests

from app.config import Settings
from app.enable_banking.types import EnableBankingSession


def get_api_base_url(settings: Settings) -> str:
    return str(settings.api_origin).rstrip("/")


def load_private_key(key_path: Path) -> str:
    with key_path.open("r", encoding="utf-8") as key_file:
        return key_file.read()


def create_enable_banking_headers(
    settings: Settings,
) -> dict[str, str]:
    issued_at = int(datetime.now(timezone.utc).timestamp())
    private_key = load_private_key(settings.key_path)

    payload = {
        "iss": "enablebanking.com",
        "aud": "api.enablebanking.com",
        "iat": issued_at,
        "exp": issued_at + 3600,
    }

    token = pyjwt.encode(
        payload,
        key=private_key,
        algorithm="RS256",
        headers={"kid": settings.application_id},
    )

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def create_bank_authorization(
    settings: Settings,
    state: str,
) -> str:
    headers = create_enable_banking_headers(settings)
    base_url = get_api_base_url(settings)

    request_body = {
        "access": {
            "valid_until": (
                datetime.now(timezone.utc) + timedelta(days=10)
            ).isoformat()
        },
        "aspsp": {
            "name": settings.aspsp_name,
            "country": settings.aspsp_country,
        },
        "state": state,
        "redirect_url": str(settings.callback_url),
        "psu_type": "personal",
    }

    response = requests.post(
        f"{base_url}/auth",
        json=request_body,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    authorization_url = response.json().get("url")

    if not authorization_url:
        raise ValueError(
            "Enable Banking response did not contain an authorization URL"
        )

    return authorization_url


def exchange_authorization_code(
    settings: Settings,
    code: str,
) -> EnableBankingSession:
    headers = create_enable_banking_headers(settings)
    base_url = get_api_base_url(settings)

    response = requests.post(
        f"{base_url}/sessions",
        json={"code": code},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    return EnableBankingSession.model_validate(response.json())


def retrieve_enable_banking_session(
    settings: Settings,
    session_id: str,
) -> EnableBankingSession:
    headers = create_enable_banking_headers(settings)
    base_url = get_api_base_url(settings)

    response = requests.get(
        f"{base_url}/sessions/{session_id}",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    return EnableBankingSession.model_validate(response.json())
