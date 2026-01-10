"""Ivideon API client."""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

import requests
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    AUTH_HOST,
    AUTH_PATH,
    AUTH_CLIENT_ID,
    CLIENT_VERSION,
    DEVICE_TYPE,
    DEVICE_INSTANCE_ID,
    TRUSTED_DEVICE,
    OPENAPI_DEFAULT,
    API4_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


def now_ts() -> int:
    """Get current timestamp."""
    return int(time.time())


def ts_to_iso(ts: Any) -> Optional[str]:
    """Convert timestamp to ISO format."""
    if ts is None:
        return None
    try:
        ts = float(ts)
    except Exception:
        return None
    if ts <= 0:
        return None
    # Handle milliseconds
    if ts > 2_000_000_000_000:
        ts = ts / 1000.0
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def normalize_cost(cost_raw: Any) -> Optional[float]:
    """Normalize cost value (convert kopecks to rubles if needed)."""
    if cost_raw is None:
        return None
    try:
        v = float(cost_raw)
    except Exception:
        return None
    # If value looks like kopecks (>= 1000), convert to rubles
    return round(v / 100.0, 2) if v >= 1000 else round(v, 2)


class IvideonAPI:
    """Ivideon API client."""

    def __init__(self, email: str, password: str) -> None:
        """Initialize the API client."""
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.access_token: str = ""
        self.refresh_token: Optional[str] = None
        self.expires_at: int = 0
        self.user_id: Optional[str] = None
        self.openapi_host: str = OPENAPI_DEFAULT
        self.api4_host: str = API4_DEFAULT

    def _save_tokens_from_payload(self, payload: Dict[str, Any]) -> None:
        """Save tokens from API response."""
        expires_in = int(payload.get("expires_in") or 0)
        expires_at = now_ts() + expires_in - 300  # -5 min buffer

        self.access_token = payload["access_token"]
        self.refresh_token = payload.get("refresh_token")
        self.expires_at = expires_at

        owner_id = payload.get("owner_id")
        self.user_id = str(owner_id) if owner_id is not None else self.user_id

        # Update hosts from token
        self.openapi_host = (
            payload.get("api_host") or payload.get("api5_host") or self.openapi_host
        )
        self.api4_host = payload.get("api4_host") or self.api4_host

    def token_valid(self) -> bool:
        """Check if current token is valid."""
        return bool(self.access_token and self.user_id and now_ts() < self.expires_at)

    async def login(self) -> None:
        """Login with email and password."""
        url = f"https://{AUTH_HOST}{AUTH_PATH}"
        params = {"client_id": AUTH_CLIENT_ID}
        data = {
            "grant_type": "password",
            "username": self.email,
            "password": self.password,
            "trusted_device": TRUSTED_DEVICE,
            "client_version": CLIENT_VERSION,
            "device_type": DEVICE_TYPE,
            "device_instance_id": DEVICE_INSTANCE_ID,
        }

        try:
            r = await self._async_post(url, params=params, data=data)
            r.raise_for_status()
            payload = r.json()

            if "access_token" not in payload:
                raise ConfigEntryAuthFailed(f"Unexpected token response: {payload}")

            self._save_tokens_from_payload(payload)
            _LOGGER.info("Successfully logged in to Ivideon")

        except requests.exceptions.HTTPError as err:
            if err.response.status_code in (401, 403):
                raise ConfigEntryAuthFailed("Invalid credentials") from err
            raise

    async def refresh_access_token(self) -> None:
        """Refresh access token using refresh token."""
        if not self.refresh_token:
            raise ConfigEntryAuthFailed("No refresh token available")

        url = f"https://{AUTH_HOST}{AUTH_PATH}"
        params = {"client_id": AUTH_CLIENT_ID}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "trusted_device": TRUSTED_DEVICE,
            "client_version": CLIENT_VERSION,
            "device_type": DEVICE_TYPE,
            "device_instance_id": DEVICE_INSTANCE_ID,
        }

        try:
            r = await self._async_post(url, params=params, data=data)
            r.raise_for_status()
            payload = r.json()

            if "access_token" not in payload:
                raise ConfigEntryAuthFailed(f"Unexpected refresh response: {payload}")

            self._save_tokens_from_payload(payload)
            _LOGGER.debug("Successfully refreshed access token")

        except requests.exceptions.HTTPError as err:
            if err.response.status_code in (401, 403):
                raise ConfigEntryAuthFailed("Refresh token expired") from err
            raise

    async def ensure_auth(self) -> None:
        """Ensure we have a valid authentication token."""
        if self.token_valid():
            return

        # Try to refresh if we have a refresh token
        if self.refresh_token:
            try:
                await self.refresh_access_token()
                if self.token_valid():
                    return
            except Exception as err:
                _LOGGER.debug("Failed to refresh token: %s", err)

        # Fall back to password login
        await self.login()

        if not self.user_id:
            raise ConfigEntryAuthFailed(
                "Login succeeded but user_id not found in response"
            )

    def _headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://my.ivideon.com",
            "Referer": "https://my.ivideon.com/",
        }

    async def _async_post(self, url: str, **kwargs) -> requests.Response:
        """Make async POST request."""
        return await self._run_in_executor(
            lambda: self.session.post(url, timeout=30, **kwargs)
        )

    async def _async_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """Make async HTTP request."""
        return await self._run_in_executor(
            lambda: self.session.request(method, url, timeout=30, **kwargs)
        )

    async def _run_in_executor(self, func):
        """Run function in executor."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func)

    async def _request_json(
        self,
        method: str,
        host: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make JSON API request."""
        url = f"https://{host}{path}"
        r = await self._async_request(
            method=method.upper(),
            url=url,
            params=params or {},
            json=json_body,
            headers=self._headers(),
        )

        try:
            data = r.json()
        except Exception:
            data = {"_http_status": r.status_code, "_raw": r.text}

        if r.status_code >= 400:
            data["_http_status"] = r.status_code
            _LOGGER.error("API request failed: %s %s - %s", method, path, data)

        return data

    async def get_servers(self) -> Dict[str, Any]:
        """Get servers and cameras information."""
        await self.ensure_auth()

        body = {
            "user": self.user_id,
            "include_all": False,
            "limit": 1000,
            "projection": {
                "id": 1,
                "name": 1,
                "cameras": {
                    "id": 1,
                    "name": 1,
                    "_misc": 1,
                },
            },
            "sort": {"name": 1},
        }

        return await self._request_json(
            "POST",
            self.openapi_host,
            "/servers",
            params={"op": "FIND"},
            json_body=body,
        )

    async def get_balance(self) -> Optional[Dict[str, Any]]:
        """Get account balance."""
        await self.ensure_auth()

        try:
            return await self._request_json("GET", self.api4_host, "/users/me/balance")
        except Exception as err:
            _LOGGER.error("Failed to get balance: %s", err)
            return None

    async def get_data(self) -> Dict[str, Any]:
        """Get all data (balance and billing info)."""
        balance = await self.get_balance()
        servers = await self.get_servers()
        billing = self._build_billing_report(servers)

        return {
            "user_id": self.user_id,
            "balance": balance,
            "billing": billing,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _build_billing_report(self, servers_json: Dict[str, Any]) -> Dict[str, Any]:
        """Build billing report from servers data."""
        items = servers_json.get("result", {}).get("items", []) or []

        cameras: List[Dict[str, Any]] = []
        expires_values: List[int] = []
        currency_any: Optional[str] = None

        for srv in items:
            for cam in srv.get("cameras") or []:
                tariff = (cam.get("_misc") or {}).get("tariff") or {}

                expires = tariff.get("expires")
                start_time = tariff.get("start_time")
                cost_raw = tariff.get("cost")
                cur = tariff.get("currency")

                if cur:
                    currency_any = cur
                if expires:
                    try:
                        expires_values.append(int(expires))
                    except Exception:
                        pass

                cameras.append(
                    {
                        "camera_name": cam.get("name"),
                        "camera_id": cam.get("id"),
                        "tariff_id": tariff.get("id"),
                        "tariff_name": tariff.get("name"),
                        "period": tariff.get("period"),
                        "payment_type": tariff.get("payment_type"),
                        "active": tariff.get("active"),
                        "expired": tariff.get("expired"),
                        "start_iso": ts_to_iso(start_time),
                        "expires_iso": ts_to_iso(expires),
                        "cost": normalize_cost(cost_raw),
                        "currency": cur,
                    }
                )

        nearest_expires = min(expires_values) if expires_values else None
        nearest_iso = ts_to_iso(nearest_expires)

        nearest_sum = 0.0
        if nearest_iso:
            for c in cameras:
                if c.get("expires_iso") == nearest_iso:
                    nearest_sum += float(c.get("cost") or 0.0)

        return {
            "nearest_payment_date": nearest_iso,
            "nearest_payment_amount_total": round(nearest_sum, 2),
            "currency": currency_any,
            "cameras_count": len(cameras),
            "cameras": cameras,
        }
