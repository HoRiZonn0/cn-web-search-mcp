"""Bounded HTTP client with proxy support and SSRF protections."""

from __future__ import annotations

import ipaddress
import json
import socket
import ssl
from dataclasses import dataclass
from time import perf_counter
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
from urllib.parse import urlsplit

from .config import Settings


class UnsafeUrlError(ValueError):
    pass


@dataclass(slots=True)
class HttpResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    elapsed_ms: int


def validate_public_url(url: str, *, allow_private: bool = False) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrlError("only absolute http/https URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("credentials in URLs are not allowed")
    if allow_private:
        return
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"}:
        raise UnsafeUrlError("local network URLs are not allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"DNS resolution failed: {hostname}") from exc
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise UnsafeUrlError(f"non-public address is not allowed: {address}")


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allow_private: bool):
        self.allow_private = allow_private
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl, allow_private=self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._proxy = {"http": settings.proxy_url, "https": settings.proxy_url} if settings.proxy_url else {}

    def _build_opener(self, allow_private: bool):
        context = ssl.create_default_context()
        return build_opener(
            ProxyHandler(self._proxy),
            HTTPSHandler(context=context),
            _SafeRedirectHandler(allow_private),
        )

    def get(
        self,
        url: str,
        *,
        timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
        trusted_network: bool = False,
    ) -> HttpResponse:
        allow_private = self.settings.allow_private_networks or trusted_network
        validate_public_url(url, allow_private=allow_private)
        request_headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        request_headers.update(headers or {})
        request = Request(url, headers=request_headers, method="GET")
        started = perf_counter()
        try:
            with self._build_opener(allow_private).open(
                request, timeout=timeout or self.settings.request_timeout_seconds
            ) as response:
                body = response.read(self.settings.max_response_bytes + 1)
                if len(body) > self.settings.max_response_bytes:
                    raise ValueError("response exceeded configured byte limit")
                final_url = response.geturl()
                validate_public_url(final_url, allow_private=allow_private)
                return HttpResponse(
                    url=final_url,
                    status_code=int(response.status),
                    headers={key.casefold(): value for key, value in response.headers.items()},
                    body=body,
                    elapsed_ms=round((perf_counter() - started) * 1000),
                )
        except HTTPError as exc:
            body = exc.read(min(self.settings.max_response_bytes, 128_000))
            return HttpResponse(
                url=exc.geturl() or url,
                status_code=int(exc.code),
                headers={key.casefold(): value for key, value in exc.headers.items()},
                body=body,
                elapsed_ms=round((perf_counter() - started) * 1000),
            )
        except (URLError, TimeoutError, OSError) as exc:
            raise ConnectionError(str(exc)) from exc

    def post_json(
        self,
        url: str,
        payload: dict,
        *,
        timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
        trusted_network: bool = False,
    ) -> HttpResponse:
        allow_private = self.settings.allow_private_networks or trusted_network
        validate_public_url(url, allow_private=allow_private)
        request_headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        request_headers.update(headers or {})
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, headers=request_headers, method="POST")
        started = perf_counter()
        try:
            with self._build_opener(allow_private).open(
                request, timeout=timeout or self.settings.request_timeout_seconds
            ) as response:
                response_body = response.read(self.settings.max_response_bytes + 1)
                if len(response_body) > self.settings.max_response_bytes:
                    raise ValueError("response exceeded configured byte limit")
                final_url = response.geturl()
                validate_public_url(final_url, allow_private=allow_private)
                return HttpResponse(
                    url=final_url,
                    status_code=int(response.status),
                    headers={key.casefold(): value for key, value in response.headers.items()},
                    body=response_body,
                    elapsed_ms=round((perf_counter() - started) * 1000),
                )
        except HTTPError as exc:
            response_body = exc.read(min(self.settings.max_response_bytes, 128_000))
            return HttpResponse(
                url=exc.geturl() or url,
                status_code=int(exc.code),
                headers={key.casefold(): value for key, value in exc.headers.items()},
                body=response_body,
                elapsed_ms=round((perf_counter() - started) * 1000),
            )
        except (URLError, TimeoutError, OSError) as exc:
            raise ConnectionError(str(exc)) from exc


def decode_body(response: HttpResponse) -> str:
    content_type = response.headers.get("content-type", "")
    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip(' "\'')
    for candidate in (charset, "utf-8", "gb18030"):
        try:
            return response.body.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return response.body.decode("utf-8", errors="replace")
