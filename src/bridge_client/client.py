"""Bearer-auth HTTP client for the bridge trace endpoints (Phase 4)."""
from __future__ import annotations

from typing import Any, Iterable, Optional

import httpx

from ..core.auth import build_auth_headers, redact_token


class BridgeAPIError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class BridgeClient:
    """Synchronous HTTP client. Async lives in the stream module so the UI
    can drive it from a background thread.

    The plan's auth rules say 401/403 must be surfaced cleanly to the UI, and
    the token must never be logged. We translate non-2xx into BridgeAPIError
    and run every payload through `redact_token` before any logging callback.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        *,
        http_client: Optional[httpx.Client] = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._http = http_client or httpx.Client(timeout=timeout)
        self._owns_http = http_client is None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "BridgeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def token(self) -> Optional[str]:
        return self._token

    def set_token(self, token: Optional[str]) -> None:
        self._token = token

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self._base_url}{path}"

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self._http.get(
                self._url(path),
                headers=build_auth_headers(self._token),
                params=params or {},
            )
        except httpx.HTTPError as exc:
            raise BridgeAPIError(f"network error talking to {path}: {exc}") from exc

        if response.status_code in (401, 403):
            raise BridgeAPIError(
                f"auth failure ({response.status_code}) for {path}", status=response.status_code
            )
        if response.status_code >= 400:
            raise BridgeAPIError(
                f"{response.status_code} from {path}: {response.text[:200]}",
                status=response.status_code,
            )
        return response.json()

    # ------------------------------------------------------------------
    # Endpoints (BridgeTracer.md "Bridge API Assumptions")
    # ------------------------------------------------------------------
    def list_events(self, *, since: str | None = None) -> list[dict[str, Any]]:
        params = {"since": since} if since else None
        return list(self._get("/trace/events", params=params))

    def list_runs(self) -> list[dict[str, Any]]:
        return list(self._get("/trace/runs"))

    def list_sessions(self) -> list[dict[str, Any]]:
        return list(self._get("/trace/sessions"))

    def fetch_file_ref(self, ref_id: str) -> tuple[str | None, int, bytes | str | None]:
        """Used as the FetcherFn for FileRefRetriever. Returns (mime, size, data)."""
        try:
            response = self._http.get(
                self._url(f"/trace/file_refs/{ref_id}"),
                headers=build_auth_headers(self._token),
            )
        except httpx.HTTPError as exc:
            raise BridgeAPIError(f"network error fetching file_ref {ref_id}: {exc}") from exc

        if response.status_code in (401, 403):
            raise BridgeAPIError(
                f"auth failure ({response.status_code}) for /trace/file_refs/{ref_id}",
                status=response.status_code,
            )
        if response.status_code >= 400:
            raise BridgeAPIError(
                f"{response.status_code} for ref {ref_id}",
                status=response.status_code,
            )

        mime = response.headers.get("content-type")
        size = int(response.headers.get("content-length") or len(response.content))
        if mime and mime.startswith("text/"):
            return mime, size, response.text
        return mime, size, response.content

    # ------------------------------------------------------------------
    # Debug aid — never returns the token, never logs it.
    # ------------------------------------------------------------------
    def safe_describe(self) -> dict[str, str]:
        return {
            "base_url": self._base_url,
            "has_token": "yes" if self._token else "no",
            "sample_headers": str(redact_token(build_auth_headers(self._token), self._token)),
        }
