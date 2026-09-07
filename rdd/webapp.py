"""Created on 2026-08-14.

the fastapi application of a reel site - the pages and the api as decided,
plus /docs and /openapi.json per the OpenAPI docs issue

Per the Delivery decision the site itself answers below /reels/; the web
server in front only proxies. Per the framed 404 issue every miss answers
the framed page. The docs are self-contained like every other page: the
swagger assets are served by the site, never by a CDN.

@author: wf
"""

import os
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from swagger_ui_bundle import swagger_ui_path

from rdd.i18n import LANGUAGES, pick_language
from rdd.rdd_site import Reel, ReelSite, Review, Reviews

TARPIT_SECONDS = 0.5
# per the Review cookie decision the browser remembers a token as a cookie
# of its own, so it may hold one per review
COOKIE_PREFIX = "review-"


class RateLimit:
    """Per-client limit on missed lookups.

    Per the Reel Review decision unknown tokens are rate-limited: every
    miss is tarpitted, and a client whose misses exceed the limit within
    the window answers 429 until the window has passed.
    """

    def __init__(self, max_misses: int = 10, window_seconds: float = 60.0):
        """Initialize the limit.

        Args:
            max_misses: the misses a client may accumulate per window.
            window_seconds: the sliding window in seconds.
        """
        self.max_misses = max_misses
        self.window_seconds = window_seconds
        self.misses: Dict[str, List[float]] = {}

    def miss(self, client: str, now: Optional[float] = None) -> bool:
        """Record a miss for the given client.

        Args:
            client: the client address the miss counts against.
            now: the time of the miss; the monotonic clock by default.

        Returns:
            True where the client is over the limit.
        """
        if now is None:
            now = time.monotonic()
        cutoff = now - self.window_seconds
        timestamps = [t for t in self.misses.get(client, []) if t > cutoff]
        timestamps.append(now)
        self.misses[client] = timestamps
        over_limit = len(timestamps) > self.max_misses
        return over_limit


def lang_of(request: Request) -> str:
    """The language of the given request.

    Per the i18n issue the default is the browser setting; an explicit
    ?lang= wins and is remembered by the cookie the response sets.

    Args:
        request: the request.

    Returns:
        the language code.
    """
    lang = pick_language(
        query_lang=request.query_params.get("lang"),
        cookie_lang=request.cookies.get("lang"),
        accept_language=request.headers.get("accept-language"),
    )
    return lang


def remember_lang(request: Request, response: HTMLResponse) -> HTMLResponse:
    """Remember an explicit language choice in the cookie.

    Args:
        request: the request whose ?lang= is the choice, if any.
        response: the response to carry the cookie.

    Returns:
        the response.
    """
    query_lang = request.query_params.get("lang")
    if query_lang in LANGUAGES:
        response.set_cookie("lang", query_lang)
    return response


def remember_right(
    request: Request, response: HTMLResponse, reviews: List[Review]
) -> HTMLResponse:
    """Remember the tokens that arrived by url in the browser.

    Per the Review cookie decision once the door is open the key can be
    left out: each token gets a cookie of its own for the days its review
    names, renewed on every visit with the token.

    Args:
        request: the request the tokens arrived with.
        response: the response to carry the cookies.
        reviews: the reviews whose tokens arrived by url.

    Returns:
        the response.
    """
    secure = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )
    for review in reviews:
        response.set_cookie(
            f"{COOKIE_PREFIX}{review.token}",
            "1",
            max_age=review.days * 24 * 3600,
            path="/",
            httponly=True,
            secure=secure,
            samesite="lax",
        )
    return response


def page_response(page: str, status: int = 200) -> HTMLResponse:
    """The given page as an html response.

    Args:
        page: the html page.
        status: the http status; 200 by default.

    Returns:
        the response; no-cache so a browser never shows a stale page.
    """
    response = HTMLResponse(page, status_code=status)
    response.headers["Cache-Control"] = "no-cache"
    return response


class ReelApp:
    """The fastapi application of a reel site.

    One instance wires the routes of one ReelSite; the app is what
    uvicorn serves and what /docs documents.
    """

    def __init__(self, site: ReelSite):
        """Initialize with the site to serve.

        Args:
            site: the reel site.
        """
        self.site = site
        self.tarpit_seconds = TARPIT_SECONDS
        self.rate_limit = RateLimit()
        self.app = FastAPI(
            title=site.config.title,
            version=site.version.version,
            description=(
                "The api of a reel site per the Delivery and Reel Review "
                "decisions: a reel and its files are served by acronym and "
                "right. Unknown tokens, unknown acronyms and denied reels "
                "answer alike - a tarpitted framed 404 - so neither tokens "
                "nor private acronyms can be probed."
            ),
            docs_url=None,
            redoc_url=None,
        )
        self.app.mount(
            "/static/swagger",
            StaticFiles(directory=swagger_ui_path),
            name="swagger",
        )
        self.add_routes()

    def not_found(self, request: Request, tarpit: bool = False) -> HTMLResponse:
        """The framed 404 response.

        Args:
            request: the request that has no page.
            tarpit: delay the answer so tokens and private acronyms
                cannot be probed; a client over the rate limit
                answers 429 instead.

        Returns:
            the framed 404 page as a response; 429 over the limit.
        """
        path = request.url.path
        lang = lang_of(request)
        page = self.site.not_found(path, lang)
        status = 404
        if tarpit:
            client = request.client.host if request.client else "?"
            if self.rate_limit.miss(client):
                status = 429
            else:
                time.sleep(self.tarpit_seconds)
        response = page_response(page, status=status)
        if status == 429:
            response.headers["Retry-After"] = str(int(self.rate_limit.window_seconds))
        return response

    def right_of(
        self, request: Request, address: str
    ) -> Tuple[Optional[Review], List[str], List[Review]]:
        """The right of the given request and the address parts.

        Per the Review cookie decision the token is given as
        /reels/<token>/... or as ?token=<token>, and a browser holds the
        tokens it remembers; the right is what all of them grant.

        Args:
            request: the request.
            address: the path after /reels/, optionally token first.

        Returns:
            the joined review right or None, the address parts with the
            path token stripped, and the reviews whose token arrived by
            url - the ones the browser is to remember.
        """
        parts = [urllib.parse.unquote(part) for part in address.split("/")]
        lookup = self.site.reviews.by_token()
        url_tokens: List[str] = []
        if parts and parts[0] in lookup:
            url_tokens.append(parts[0])
            parts = parts[1:]
        query_token = request.query_params.get("token")
        if query_token:
            url_tokens.append(query_token)
        cookie_tokens = [
            name[len(COOKIE_PREFIX) :]
            for name in request.cookies
            if name.startswith(COOKIE_PREFIX)
        ]
        url_reviews = self.site.reviews.by_tokens(url_tokens)
        reviews = url_reviews + self.site.reviews.by_tokens(cookie_tokens)
        review = Reviews.union(reviews)
        return review, parts, url_reviews

    def checked_reel(
        self, request: Request, address: str
    ) -> Tuple[Optional[Reel], Optional[Review], List[str]]:
        """The reel of the given address where the right allows it.

        Args:
            request: the request carrying the right.
            address: the path after /reels/, optionally token first.

        Returns:
            reel, review and remaining parts; reel is None where the
            address resolves to nothing the right allows.
        """
        review, parts, _url_reviews = self.right_of(request, address)
        reel, file_parts = self.site.resolve_reel(parts)
        if reel is not None and not self.site.allowed(reel, review):
            reel = None
        return reel, review, file_parts

    def add_routes(self) -> None:
        """Wire the routes of the site."""
        app = self.app
        site = self.site

        @app.get("/", response_class=HTMLResponse, summary="the home page")
        @app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
        def home(request: Request) -> HTMLResponse:
            """The home page - what this site is and the ways in."""
            lang = lang_of(request)
            return remember_lang(request, page_response(site.home(lang)))

        @app.get("/reels", response_class=HTMLResponse, summary="the reels directory")
        def reels(request: Request) -> HTMLResponse:
            """The reels directory as the holder of the right sees it."""
            lang = lang_of(request)
            review, _parts, url_reviews = self.right_of(request, "")
            response = page_response(site.reels(review, lang=lang))
            remember_right(request, response, url_reviews)
            return remember_lang(request, response)

        @app.get("/about", response_class=HTMLResponse, summary="the about page")
        def about(request: Request) -> HTMLResponse:
            """The about page - version, license and repository."""
            lang = lang_of(request)
            return remember_lang(request, page_response(site.about(lang)))

        @app.get("/docs", include_in_schema=False)
        def docs() -> HTMLResponse:
            """The api documentation - swagger assets served by the site."""
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title=f"{site.config.title} - api",
                swagger_js_url="/static/swagger/swagger-ui-bundle.js",
                swagger_css_url="/static/swagger/swagger-ui.css",
                swagger_favicon_url="/static/swagger/favicon-32x32.png",
            )

        @app.get(
            "/reels/{address:path}/api/files",
            summary="the files of a reel",
        )
        def api_files(address: str, request: Request):
            """The sorted file names of the reel - the review page's read api."""
            reel, _review, file_parts = self.checked_reel(request, address)
            if reel is None or file_parts:
                return self.not_found(request, tarpit=True)
            return JSONResponse(site.reel_files(reel))

        @app.get(
            "/reels/{address:path}/api/info",
            summary="folder and acronym of a reel",
        )
        def api_info(address: str, request: Request):
            """Folder and acronym of the reel."""
            reel, _review, file_parts = self.checked_reel(request, address)
            if reel is None or file_parts:
                return self.not_found(request, tarpit=True)
            return JSONResponse({"folder": reel.folder, "acronym": reel.acronym})

        @app.get(
            "/reels/{address:path}/api/reel",
            summary="the hop set of a reel",
        )
        def api_reel(address: str, request: Request):
            """The hop set parsed by the model - the page never parses YAML."""
            reel, _review, file_parts = self.checked_reel(request, address)
            if reel is None or file_parts:
                return self.not_found(request, tarpit=True)
            return JSONResponse(reel.hop_set.to_dict() if reel.hop_set else {})

        @app.get(
            "/reels/{address:path}/api/zip",
            summary="the reel folder as one zip",
        )
        def api_zip(address: str, request: Request):
            """The reel folder zipped - the verdict page's download per the
            Reel verdict decision."""
            reel, _review, file_parts = self.checked_reel(request, address)
            if reel is None or file_parts:
                return self.not_found(request, tarpit=True)
            zip_path = site.reel_zip(reel)
            return FileResponse(
                zip_path,
                media_type="application/zip",
                filename=f"{reel.acronym}.zip",
                background=BackgroundTask(os.remove, zip_path),
            )

        @app.post(
            "/reels/{address:path}/api/{action}",
            summary="the write api - true inspection mode",
        )
        async def api_write(address: str, action: str, request: Request):
            """Per the Reel Review decision a save on this site answers success
            and stores nothing; the request must name an allowed reel, so the
            write api reveals no more than the read api."""
            reel, _review, file_parts = self.checked_reel(request, address)
            if (
                reel is None
                or file_parts
                or action not in ("save", "feedback", "upload")
            ):
                return self.not_found(request, tarpit=True)
            await request.body()
            return JSONResponse({})

        @app.get(
            "/reels/{rest:path}",
            response_class=HTMLResponse,
            summary="a reel, its review or one of its files",
        )
        def reel_route(rest: str, request: Request):
            """Delivery per the Delivery and Hop url decisions.

            The url is /reels/[token/][yyyy/mm/]acronym/[file|review|hop-slug],
            optionally carrying ?token=. A bare token answers the reels
            directory of its review. Per the Review cookie decision a
            token that arrived by url is remembered by the browser.
            """
            path = request.url.path
            lang = lang_of(request)
            review, parts, url_reviews = self.right_of(request, rest)
            if not parts or parts == [""]:
                response = page_response(site.reels(review, lang=lang))
                remember_right(request, response, url_reviews)
                return remember_lang(request, response)
            reel, file_parts = site.resolve_reel(parts)
            if reel is None or not site.allowed(reel, review):
                return self.not_found(request, tarpit=True)
            if not file_parts:
                if not path.endswith("/"):
                    # the reel page needs its trailing slash so its relative
                    # review and file links resolve below the reel
                    return RedirectResponse(path + "/", status_code=301)
                response = page_response(site.reel_page(reel, lang))
            elif file_parts in (["review"], ["reelreview.html"], ["verdict"]):
                response = page_response(site.review_page(lang))
            elif len(file_parts) == 1 and file_parts[0] in reel.hop_slugs():
                response = page_response(site.review_page(lang))
            else:
                response = None
            if response is not None:
                remember_right(request, response, url_reviews)
                return remember_lang(request, response)
            file_path = os.path.realpath(os.path.join(reel.path, *file_parts))
            reel_dir = os.path.realpath(reel.path)
            if not file_path.startswith(reel_dir + os.sep) or not os.path.isfile(
                file_path
            ):
                return self.not_found(request)
            return FileResponse(file_path)

        @app.exception_handler(404)
        async def framed_404(request: Request, _exception) -> HTMLResponse:
            """Any miss answers the framed 404 page."""
            page = site.not_found(request.url.path, lang_of(request))
            return page_response(page, status=404)


class InstallationApp:
    """The installation mode application.

    Per the Owner bootstrap decision a site without reviews.yaml refuses
    to serve reels and names the init command on every request - the
    state is shown, never hidden behind a dead backend.
    """

    def __init__(self, page: str):
        """Initialize with the installation page.

        Args:
            page: the installation mode page.
        """
        self.page = page
        self.app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        self.add_routes()

    def add_routes(self) -> None:
        """Every request answers the installation state."""
        app = self.app
        page = self.page

        @app.api_route("/{rest:path}", methods=["GET", "POST"], include_in_schema=False)
        def installation(rest: str) -> HTMLResponse:
            """The installation mode state as service unavailable."""
            return page_response(page, status=503)


def create_app(site: ReelSite) -> FastAPI:
    """Create the fastapi application of the given site.

    Args:
        site: the reel site.

    Returns:
        the application.
    """
    app = ReelApp(site).app
    return app


def create_installation_app(page: str) -> FastAPI:
    """Create the installation mode application.

    Args:
        page: the installation mode page.

    Returns:
        the application.
    """
    app = InstallationApp(page).app
    return app
