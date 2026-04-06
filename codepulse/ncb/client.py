"""NCBClient — async HTTP client for NoCodeBackend data API."""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

NCB_BASE = "https://app.nocodebackend.com/api/data"
NCB_INSTANCE = "36905_codepulse_db"
NCB_TOKEN = "0f6a97716184a68e4ca67823033cf599cb0cfa59c5de7fd87f8a42f05819"

logger = logging.getLogger(__name__)


class NCBClient:
    """Low-level async client for NCB data API.

    All methods fail silently — NCB is a convenience layer, never a blocker.
    """

    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {NCB_TOKEN}",
            "X-Database-Instance": NCB_INSTANCE,
            "Content-Type": "application/json",
        }
        self._params: dict[str, Any] = {"instance": NCB_INSTANCE}

    async def create(self, table: str, data: dict[str, Any]) -> Optional[dict]:
        """Insert a record. Returns created record dict or None on failure."""
        url = f"{NCB_BASE}/create/{table}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    url, headers=self._headers, params=self._params, json=data
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "NCB create %s → HTTP %d: %s", table, resp.status_code, resp.text[:200]
                )
                return None
        except Exception as exc:
            logger.debug("NCB create %s failed: %s", table, exc)
            return None

    async def read(
        self,
        table: str,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Read records from a table. Returns [] on failure."""
        url = f"{NCB_BASE}/read/{table}"
        params: dict[str, Any] = {**self._params, "limit": limit}
        if filters:
            params.update(filters)
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=self._headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict):
                        return data.get("data", data.get("records", []))
                    return data if isinstance(data, list) else []
                logger.warning("NCB read %s → HTTP %d", table, resp.status_code)
                return []
        except Exception as exc:
            logger.debug("NCB read %s failed: %s", table, exc)
            return []

    async def update(self, table: str, record_id: str, data: dict[str, Any]) -> bool:
        """Update a record by id. Returns True on success."""
        url = f"{NCB_BASE}/update/{table}/{record_id}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.put(
                    url, headers=self._headers, params=self._params, json=data
                )
                return resp.status_code in (200, 204)
        except Exception as exc:
            logger.debug("NCB update %s/%s failed: %s", table, record_id, exc)
            return False
