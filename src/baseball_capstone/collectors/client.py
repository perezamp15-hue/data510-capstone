"""Reusable HTTP client for MLB data collection."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from baseball_capstone.config.settings import get_settings


LOGGER = logging.getLogger(__name__)


class MLBAPIError(RuntimeError):
    """Raised when MLB data cannot be retrieved or validated."""


class MLBAPIClient:
    """HTTP client for MLB Stats API endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        settings = get_settings()

        self.base_url = (
            base_url or settings.mlb_api_base_url
        ).rstrip("/")

        self.timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(settings.request_timeout_seconds)
        )

        self.max_retries = (
            int(max_retries)
            if max_retries is not None
            else int(settings.request_max_retries)
        )

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "data510-baseball-capstone/0.1 "
                    "(academic analytics project)"
                ),
            },
        )

    def __enter__(self) -> MLBAPIClient:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Request a JSON object from an MLB endpoint."""
        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"

        retrying_request = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=1,
                max=10,
            ),
            retry=retry_if_exception_type(
                (
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                )
            ),
            reraise=True,
        )(self._get_json_once)

        try:
            return retrying_request(endpoint, params or {})
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            response_preview = exc.response.text[:500]

            raise MLBAPIError(
                f"MLB API returned HTTP {status_code} for "
                f"{exc.request.url}. Response: {response_preview}"
            ) from exc
        except httpx.HTTPError as exc:
            raise MLBAPIError(
                f"MLB API request failed for endpoint {endpoint}: {exc}"
            ) from exc

    def _get_json_once(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        LOGGER.info(
            "Requesting MLB endpoint %s with parameters %s",
            endpoint,
            params,
        )

        response = self._client.get(endpoint, params=params)
        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError as exc:
            raise MLBAPIError(
                f"MLB endpoint {endpoint} returned invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise MLBAPIError(
                f"Expected a JSON object from {endpoint}, "
                f"received {type(payload).__name__}."
            )

        return payload