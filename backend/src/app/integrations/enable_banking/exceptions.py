import requests
from fastapi import HTTPException, status
from pydantic import ValidationError


def to_enable_banking_http_exception(
    exc: requests.RequestException | ValidationError,
) -> HTTPException:
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Enable Banking returned data that didn't match the expected shape",
                "errors": exc.errors(),
            },
        )

    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Enable Banking rejected the request",
                "upstream_status": exc.response.status_code,
                "upstream_body": exc.response.text[:1000],
            },
        )

    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
