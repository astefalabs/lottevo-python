"""The Lottevo API client: transport, errors and pagination."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlencode

from ._resources import Resources

__version__ = "0.2.0"

DEFAULT_BASE_URL = "https://api.lottevo.com/v1"


class LottevoError(Exception):
    """A refused or failed call.

    Branch on ``code`` (``lottery_not_entitled``, ``quota_exceeded``, ...) —
    the message is translated and will change. ``status`` is 0 when the API
    was never reached.
    """

    def __init__(
        self,
        message: str,
        status: int = 0,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        retry_after: Optional[int] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.request_id = request_id
        self.retry_after = retry_after
        self.body = body


class Client(Resources):
    """The Lottevo API client.

    Every operation hangs off a resource — ``client.lotteries.draws("EU-002")``
    — and returns the decoded JSON. The key defaults to the LOTTEVO_API_KEY
    environment variable; ``locale`` is sent as Accept-Language.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        locale: Optional[str] = None,
        timeout: float = 30,
    ) -> None:
        api_key = api_key or os.environ.get("LOTTEVO_API_KEY")
        if not api_key:
            raise ValueError("Pass an api_key or set the LOTTEVO_API_KEY environment variable.")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._locale = locale
        self._timeout = timeout
        self.last_headers: Dict[str, str] = {}
        self._boot_resources()

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Send one call and decode its JSON.

        A list value in ``params`` is sent comma-separated, the way the API
        reads ``filter[lottery]=EU-002,RO-001``; ``{"filter": {"lottery": "EU-002"}}``
        and ``{"filter[lottery]": "EU-002"}`` are the same.
        """
        query = urlencode(_flatten(params or {}))
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": f"lottevo-python/{__version__}",
        }
        if self._locale:
            headers["Accept-Language"] = self._locale
        data = None
        if body:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()

        request = urllib.request.Request(
            f"{self._base_url}{path}{'?' + query if query else ''}", data=data, headers=headers, method=method
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                status, raw = response.status, response.read()
                self.last_headers = {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
            self.last_headers = {k.lower(): v for k, v in error.headers.items()}
        except (urllib.error.URLError, OSError) as error:
            raise LottevoError(f"Could not reach the Lottevo API: {error}", code="network_error") from error

        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = None

        if status >= 400 or not isinstance(payload, dict):
            payload = payload if isinstance(payload, dict) else {}
            retry_after = payload.get("retry_after", self.last_headers.get("retry-after"))
            raise LottevoError(
                payload.get("message", f"The Lottevo API answered {status}."),
                status=status,
                code=payload.get("code"),
                request_id=self.last_headers.get("x-request-id"),
                retry_after=int(retry_after) if retry_after is not None else None,
                body=payload,
            )

        return payload

    def paginate(self, page: Dict[str, Any]) -> Iterator[Any]:
        """Every item of a listing, following ``links.next`` from the page given.

        ``for draw in client.paginate(client.draws.list()): ...``
        """
        while True:
            yield from page.get("data") or []

            next_url = (page.get("links") or {}).get("next")
            if not next_url:
                return

            # The key is only ever sent to the host the client was built for.
            if not next_url.startswith(self._base_url + "/"):
                raise LottevoError(
                    f"Refusing to follow a next page outside {self._base_url}: {next_url}",
                    code="unexpected_next_page",
                )

            page = self.request("GET", next_url[len(self._base_url):])


def _flatten(values: Dict[str, Any], prefix: Optional[str] = None) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for key, value in values.items():
        name = f"{prefix}[{key}]" if prefix else key
        if value is None:
            continue
        if isinstance(value, dict):
            pairs.extend(_flatten(value, name))
        elif isinstance(value, (list, tuple)):
            pairs.append((name, ",".join(str(item) for item in value)))
        elif isinstance(value, bool):
            pairs.append((name, "true" if value else "false"))
        else:
            pairs.append((name, str(value)))
    return pairs
