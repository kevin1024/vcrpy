import functools
import inspect
from base64 import b64encode
from collections import defaultdict
from contextlib import suppress
from contextvars import ContextVar
from email.message import Message
from http.cookiejar import CookieJar, DefaultCookiePolicy, eff_request_host
from http.cookies import CookieError, SimpleCookie, _unquote
from ipaddress import ip_address
from types import SimpleNamespace
from urllib.parse import urlsplit
from urllib.request import Request as CookieRequest

from curl_cffi import Curl
from curl_cffi.requests import Cookies, Headers, Response
from curl_cffi.requests.utils import set_curl_options

from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.request import Request

_native_bypass = ContextVar("vcr_curl_cffi_bypass", default=False)


class _CurlCookiePolicy(DefaultCookiePolicy):
    def domain_return_ok(self, domain, request):
        return domain.lstrip(".") == urlsplit(request.full_url).hostname or super().domain_return_ok(
            domain,
            request,
        )

    def return_ok_domain(self, cookie, request):
        host = urlsplit(request.full_url).hostname
        domain = cookie.domain.lstrip(".")
        return host == domain or (cookie.domain_specified and host.endswith("." + domain))

    def return_ok_secure(self, cookie, request):
        return urlsplit(request.full_url).hostname in (
            "localhost",
            "127.0.0.1",
            "::1",
        ) or super().return_ok_secure(cookie, request)


class _ReplayCookiePolicy(DefaultCookiePolicy):
    def set_ok_domain(self, cookie, request):
        return cookie.domain.lstrip(".") == urlsplit(request.full_url).hostname or super().set_ok_domain(
            cookie,
            request,
        )


class _ReplayCookieJar(CookieJar):
    def __init__(self, request):
        super().__init__(policy=_ReplayCookiePolicy())
        self.host = urlsplit(request.full_url).hostname
        self.effective_host = eff_request_host(request)[1]
        try:
            ip_address(self.host)
            self.ip_host = True
        except ValueError:
            self.ip_host = False

    def _cookie_from_cookie_tuple(self, value, request):
        if path := value[2].get("path"):
            value[2]["path"] = _unquote(path)
        cookie = super()._cookie_from_cookie_tuple(value, request)
        if cookie is not None:
            if cookie.value is None:
                return None
            if cookie.name.startswith(("__Secure-", "__Host-")) and (
                not cookie.secure
                or (cookie.name.startswith("__Host-") and (cookie.domain_specified or cookie.path != "/"))
            ):
                return None
            if not cookie.domain_specified or (self.ip_host and cookie.domain.lstrip(".") == self.host):
                cookie.domain = self.host
                cookie.domain_specified = cookie.domain_initial_dot = False
            if not cookie.path.startswith("/"):
                cookie.path = "/"
            if cookie.domain_specified and self._policy.set_ok(cookie, request):
                self.clear(cookie.domain, cookie.path, cookie.name)
            cookie.value = _unquote(cookie.value)
        return cookie

    def clear(self, domain=None, path=None, name=None):
        if domain == self.effective_host or (
            self.ip_host and domain is not None and domain.lstrip(".") == self.host
        ):
            domain = self.host
        if path is not None and not path.startswith("/"):
            path = "/"
        for candidate in (domain, domain[1:]) if domain and domain.startswith(".") else (domain,):
            with suppress(KeyError):
                super().clear(candidate, path, name)


def _without_native_cassette(function):
    """Run ``function`` without the native curl_cffi patch so a wrapping stub records the request once."""

    @functools.wraps(function)
    def sync_call(*args, **kwargs):
        token = _native_bypass.set(True)
        try:
            return function(*args, **kwargs)
        finally:
            _native_bypass.reset(token)

    @functools.wraps(function)
    async def async_call(*args, **kwargs):
        token = _native_bypass.set(True)
        try:
            return await function(*args, **kwargs)
        finally:
            _native_bypass.reset(token)

    return async_call if inspect.iscoroutinefunction(function) else sync_call


class _BufferedResponse(Response):
    def iter_content(self, chunk_size=None, decode_unicode=False):
        if decode_unicode:
            raise NotImplementedError
        if not self._stream_closed:
            try:
                if self.content:
                    yield self.content
            finally:
                self.close()

    async def aiter_content(self, chunk_size=None, decode_unicode=False):
        for chunk in self.iter_content(chunk_size, decode_unicode):
            yield chunk

    def close(self):
        self._stream_closed = True

    async def aclose(self):
        self.close()


def _buffer_response(response, body):
    buffered = _BufferedResponse()
    buffered.__dict__.update(vars(response))
    for field in ("curl", "queue", "stream_task", "astream_task", "quit_now"):
        setattr(buffered, field, None)
    buffered.content = body
    buffered._stream_closed = False
    return buffered


def _prepare_request(session, signature, args, kwargs):
    session._check_session_closed()
    options = signature.bind(session, *args, **kwargs).arguments
    positions = {
        name: value.tell()
        for name in ("data", "content")
        if (value := options.get(name)) is not None and getattr(value, "seekable", lambda: False)()
    }
    curl = Curl()
    try:
        request, *_ = set_curl_options(
            curl,
            method=options["method"],
            url=options["url"],
            params_list=[session.params, options.get("params")],
            base_url=session.base_url,
            data=options.get("data"),
            content=options.get("content"),
            json=options.get("json"),
            headers_list=[session.headers, options.get("headers")],
            cookies_list=[session.cookies, options.get("cookies")],
            proxies_list=[None, None],
            verify_list=[True, None],
            quote=options.get("quote", ""),
        )
        if "content" in positions:
            request.body = options["content"].read()
    finally:
        for name, position in positions.items():
            options[name].seek(position)
        curl.close()
    _complete_headers(session, request, options)
    return request, options


def _complete_headers(session, request, options):
    request.headers.pop("Expect", None)
    data = options.get("content") if options.get("content") is not None else options.get("data")
    if "content-type" not in request.headers:
        if options.get("json") is not None:
            request.headers["Content-Type"] = "application/json"
        elif isinstance(data, (str, bytes, bytearray)) and data:
            request.headers["Content-Type"] = "application/octet-stream"
        elif not hasattr(options.get("content"), "read") and (
            isinstance(data, dict) or request.body or request.method in ("POST", "PUT", "PATCH")
        ):
            request.headers["Content-Type"] = "application/x-www-form-urlencoded"
    auth = options.get("auth") or session.auth
    if auth and "authorization" not in request.headers:
        request.headers["Authorization"] = "Basic " + b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    if options.get("referer") and "referer" not in request.headers:
        request.headers["Referer"] = options["referer"]
    cookies = Cookies(session.cookies)
    cookies.update(options.get("cookies") or {})
    jar = CookieJar(policy=_CurlCookiePolicy())
    for morsel in cookies.get_cookies_for_curl(request):
        jar.set_cookie(morsel.to_cookiejar_cookie())
    cookie_request = CookieRequest(request.url, headers=dict(request.headers))
    jar.add_cookie_header(cookie_request)
    cookie_header = cookie_request.get_header("Cookie")
    if cookie_header is not None:
        request.headers["Cookie"] = cookie_header


def _restore_cookies(session, response, options):
    message = Message()
    for name, value in response.headers.multi_items():
        message[name] = value
    cookie_request = CookieRequest(response.url)
    cookie_response = SimpleNamespace(info=lambda: message)
    if not (session.discard_cookies or options.get("discard_cookies", False)):
        jar = _ReplayCookieJar(cookie_request)
        for cookie in session.cookies.jar:
            jar.set_cookie(cookie)
        jar.extract_cookies(cookie_response, cookie_request)
        session.cookies.jar.clear()
        for cookie in jar:
            session.cookies.jar.set_cookie(cookie)
    for header in response.headers.get_list("set-cookie"):
        try:
            parsed = SimpleCookie(header)
        except CookieError:
            continue
        for name, morsel in parsed.items():
            response.cookies.set(
                name,
                morsel.value,
                domain=morsel["domain"],
                path=morsel["path"],
                secure=bool(morsel["secure"]),
            )


def _replay_response(session, request, stored, options):
    response = _BufferedResponse(request=request)
    response.status_code = stored["status"]["code"]
    response.reason = stored["status"].get("message", "")
    response.ok = 200 <= response.status_code < 400
    response.url = stored.get("url", request.url)
    response.headers = Headers(
        [(name, value) for name, values in stored["headers"].items() for value in values],
    )
    body = stored["body"]["string"]
    response.content = body.encode("utf-8") if isinstance(body, str) else body or b""
    response.default_encoding = options.get("default_encoding", "utf-8")
    _restore_cookies(session, response, options)
    if session.raise_for_status:
        response.raise_for_status()
    return response


def _select_response(cassette, session, request, options):
    vcr_request = Request(request.method, request.url, request.body or b"", dict(request.headers))
    if cassette.can_play_response_for(vcr_request):
        stored = cassette.play_response(vcr_request)
        return vcr_request, _replay_response(session, request, stored, options)
    if cassette.write_protected and cassette.filter_request(vcr_request):
        raise CannotOverwriteExistingCassetteException(cassette=cassette, failed_request=vcr_request)
    return vcr_request, None


def _record_response(cassette, request, response, body):
    headers = defaultdict(list)
    for name, value in response.headers.multi_items():
        headers[name].append(value)
    cassette.append(
        request,
        {
            "status": {"code": response.status_code, "message": response.reason},
            "headers": dict(headers),
            "body": {"string": body},
            "url": response.url,
        },
    )


def vcr_request(cassette, real_request):
    """Wrap ``curl_cffi`` ``Session.request`` or ``AsyncSession.request`` so that it uses ``cassette``.

    The request is rebuilt the way curl_cffi sends it (base URL, params, headers, cookies, auth,
    referer and body) before it is matched. Streaming responses are read fully and buffered.
    """
    signature = inspect.signature(real_request)

    @functools.wraps(real_request)
    def sync_request(session, *args, **kwargs):
        if _native_bypass.get():
            return real_request(session, *args, **kwargs)
        request, options = _prepare_request(session, signature, args, kwargs)
        vcr_request, response = _select_response(cassette, session, request, options)
        if response is not None:
            return response
        response = real_request(session, *args, **kwargs)
        if options.get("stream"):
            try:
                body = b"".join(response.iter_content())
            finally:
                response.close()
            response = _buffer_response(response, body)
        else:
            body = response.content
        _record_response(cassette, vcr_request, response, body)
        return response

    @functools.wraps(real_request)
    async def async_request(session, *args, **kwargs):
        if _native_bypass.get():
            return await real_request(session, *args, **kwargs)
        request, options = _prepare_request(session, signature, args, kwargs)
        vcr_request, response = _select_response(cassette, session, request, options)
        if response is not None:
            return response
        response = await real_request(session, *args, **kwargs)
        if options.get("stream"):
            try:
                body = b"".join([chunk async for chunk in response.aiter_content()])
            finally:
                await response.aclose()
            response = _buffer_response(response, body)
        else:
            body = response.content
        _record_response(cassette, vcr_request, response, body)
        return response

    return async_request if inspect.iscoroutinefunction(real_request) else sync_request
