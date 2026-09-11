from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import jwt as pyjwt
import requests

from app.core.config import Settings
from app.integrations.enable_banking.schemas import (
    CreatedEnableBankingSession,
    EnableBankingBalance,
    EnableBankingTransactions,
)


def get_api_base_url(settings: Settings) -> str:
    return str(settings.api_origin).rstrip("/")


def load_private_key(key_path: Path) -> str:
    with key_path.open("r", encoding="utf-8") as key_file:
        return key_file.read()


def create_enable_banking_headers(
    settings: Settings,
) -> dict[str, str]:
    issued_at = int(datetime.now(UTC).timestamp())
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


def list_aspsps(settings: Settings, country: str) -> list[dict]:
    headers = create_enable_banking_headers(settings)
    base_url = get_api_base_url(settings)

    response = requests.get(
        f"{base_url}/aspsps",
        params={"country": country},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("aspsps", [])


def create_bank_authorization(
    settings: Settings,
    state: str,
    aspsp_name: str,
    aspsp_country: str,
) -> str:
    headers = create_enable_banking_headers(settings)
    base_url = get_api_base_url(settings)

    request_body = {
        "access": {
            "valid_until": (
                datetime.now(UTC) + timedelta(days=10)
            ).isoformat()
        },
        "aspsp": {
            "name": aspsp_name,
            "country": aspsp_country,
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
) -> CreatedEnableBankingSession:
    response = requests.post(
        f"{get_api_base_url(settings)}/sessions",
        json={"code": code},
        headers=create_enable_banking_headers(settings),
        timeout=30,
    )
    response.raise_for_status()

    return CreatedEnableBankingSession.model_validate(
        response.json()
    )

def retrieve_account_balances(
    settings: Settings,
    account_id: str,
) -> EnableBankingBalance:
    response = requests.get(
        f"{get_api_base_url(settings)}/accounts/{account_id}/balances",
        headers=create_enable_banking_headers(settings),
        timeout=30,
    )
    response.raise_for_status()

    return EnableBankingBalance.model_validate(response.json())

def retrieve_account_transactions(
    settings: Settings,
    account_id: str,
    continuation_key: str | None = None,
    date_from: date | None = None,
) -> EnableBankingTransactions:
    response = requests.get(
        f"{get_api_base_url(settings)}/accounts/{account_id}/transactions",
        headers=create_enable_banking_headers(settings),
        timeout=30,
        params={
            "continuation_key": continuation_key,
            "date_from": date_from.isoformat() if date_from else None,
        },
    )
    response.raise_for_status()
    
    return EnableBankingTransactions.model_validate(response.json())

def delete_enable_banking_session(settings: Settings, session_id: str) -> None:
    response = requests.delete(
        f"{get_api_base_url(settings)}/sessions/{session_id}",
        headers=create_enable_banking_headers(settings),
        timeout=30,
    )
    response.raise_for_status()