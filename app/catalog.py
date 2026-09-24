"""Fetch and cache the Go rules catalog (GET /meta/rules) with ETag support."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_CLOUD9_API_URL = "http://localhost:8080"


class RulesCatalogClient:
    """In-process ETag cache for the public rules catalog."""

    def __init__(self, base_url: str | None = None, client: httpx.Client | None = None) -> None:
        self._base_url = (base_url or os.getenv("CLOUD9_API_URL", DEFAULT_CLOUD9_API_URL)).rstrip("/")
        self._client = client
        self._etag: str | None = None
        self._body: dict[str, Any] | None = None

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(base_url=self._base_url, timeout=30.0)

    def fetch(self) -> dict[str, Any]:
        """Return the rules catalog JSON, reusing cache on 304 Not Modified."""
        headers: dict[str, str] = {}
        if self._etag:
            headers["If-None-Match"] = self._etag

        owned = self._client is None
        client = self._http()
        try:
            response = client.get("/meta/rules", headers=headers)
            if response.status_code == 304:
                if self._body is None:
                    raise RuntimeError("rules catalog 304 without cached body")
                return self._body
            response.raise_for_status()
            etag = response.headers.get("ETag")
            if etag:
                self._etag = etag
            self._body = response.json()
            return self._body
        finally:
            if owned:
                client.close()

    def clear_cache(self) -> None:
        self._etag = None
        self._body = None


_default_client: RulesCatalogClient | None = None


def get_rules_catalog_client() -> RulesCatalogClient:
    global _default_client
    if _default_client is None:
        _default_client = RulesCatalogClient()
    return _default_client


def set_rules_catalog_client(client: RulesCatalogClient | None) -> None:
    global _default_client
    _default_client = client
